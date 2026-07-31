"""Download-on-demand caching, per design doc section 1.3: explicit path >
CCAMLRGIS_CACHE_DIR env var > platformdirs cache dir. Every fetch uses a
conditional request (ETag/Last-Modified), writes atomically (temp file then
rename), and records a checksum in manifest.json next to the data.
"""

import hashlib
import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import platformdirs
import requests


class CCAMLRGISOfflineError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(
            f"Could not fetch '{name}' and no cached copy is available. "
            "Run ccamlrgis.cache.prefetch() while online, or point "
            "CCAMLRGIS_CACHE_DIR at an existing cache."
        )
        self.name = name


def cache_dir(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    env = os.environ.get("CCAMLRGIS_CACHE_DIR")
    if env:
        return Path(env)
    return Path(platformdirs.user_cache_dir("ccamlrgis"))


def _manifest_path(directory: Path) -> Path:
    return directory / "manifest.json"


def _load_manifest(directory: Path) -> dict[str, Any]:
    p = _manifest_path(directory)
    return json.loads(p.read_text()) if p.exists() else {}


def _save_manifest(directory: Path, manifest: dict[str, Any]) -> None:
    _manifest_path(directory).write_text(json.dumps(manifest, indent=2, sort_keys=True))


def fetch(
    url: str, name: str, path: str | Path | None = None, force_refresh: bool = False, timeout: float = 60
) -> Path:
    """Download `url` to the cache dir under `name`, using a conditional
    request when a cached copy already exists. Returns the local path.
    Raises CCAMLRGISOfflineError if the request fails and there's no usable
    cached copy to fall back to.
    """
    directory = cache_dir(path)
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / name
    manifest = _load_manifest(directory)
    entry = manifest.get(name, {})

    headers = {}
    if not force_refresh and dest.exists():
        if entry.get("etag"):
            headers["If-None-Match"] = entry["etag"]
        if entry.get("last_modified"):
            headers["If-Modified-Since"] = entry["last_modified"]

    try:
        resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
        if resp.status_code == 304:
            return dest
        resp.raise_for_status()
    except requests.RequestException as exc:
        if dest.exists():
            return dest
        raise CCAMLRGISOfflineError(name) from exc

    fd, tmp_path = tempfile.mkstemp(dir=directory)
    digest = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                f.write(chunk)
                digest.update(chunk)
        os.replace(tmp_path, dest)
    except Exception:
        os.unlink(tmp_path)
        raise

    manifest[name] = {
        "url": url,
        "etag": resp.headers.get("ETag"),
        "last_modified": resp.headers.get("Last-Modified"),
        "sha256": digest.hexdigest(),
        "bytes": dest.stat().st_size,
    }
    _save_manifest(directory, manifest)
    return dest


def info(path: str | Path | None = None) -> dict[str, Any]:
    """Return the cache manifest: name -> {url, etag, last_modified, sha256, bytes}."""
    return _load_manifest(cache_dir(path))


def prefetch(layers: Sequence[str] | None = None, bathy_res: int | None = None, path: str | Path | None = None) -> None:
    """Warm the cache for the given WFS layer names (see load.py) and,
    optionally, a bathymetry resolution, so the library can be used offline
    afterwards.
    """
    from . import load as _load

    fns = {
        "asds": _load.load_asds,
        "ssrus": _load.load_ssrus,
        "coastline": _load.load_coastline,
        "rbs": _load.load_rbs,
        "ssmus": _load.load_ssmus,
        "mas": _load.load_mas,
        "mpas": _load.load_mpas,
        "eezs": _load.load_eezs,
    }
    for name in layers or []:
        if name not in fns:
            raise ValueError(f"Unknown layer '{name}'; choose from {sorted(fns)}")
        fns[name](path=path)
    if bathy_res is not None:
        _load.load_bathy(res=bathy_res, path=path)
