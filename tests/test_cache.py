import json

from ccamlrgis import cache


def test_cache_dir_resolution_order(tmp_path, monkeypatch):
    monkeypatch.delenv("CCAMLRGIS_CACHE_DIR", raising=False)
    explicit = tmp_path / "explicit"
    assert cache.cache_dir(path=explicit) == explicit

    env_dir = tmp_path / "env"
    monkeypatch.setenv("CCAMLRGIS_CACHE_DIR", str(env_dir))
    assert cache.cache_dir() == env_dir

    monkeypatch.delenv("CCAMLRGIS_CACHE_DIR")
    assert cache.cache_dir() != env_dir  # falls through to platformdirs


def test_fetch_writes_manifest_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.delenv("CCAMLRGIS_CACHE_DIR", raising=False)

    calls = []

    class FakeResponse:
        status_code = 200

        def __init__(self):
            self.headers = {"ETag": '"abc123"', "Last-Modified": "Wed, 01 Jan 2026 00:00:00 GMT"}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield b"hello world"

    def fake_get(url, headers=None, timeout=None, stream=None):
        calls.append(headers or {})
        return FakeResponse()

    monkeypatch.setattr(cache.requests, "get", fake_get)

    dest = cache.fetch("https://example.com/data.json", name="data.json", path=tmp_path)
    assert dest.read_bytes() == b"hello world"

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["data.json"]["etag"] == '"abc123"'
    assert manifest["data.json"]["bytes"] == len(b"hello world")

    cache.fetch("https://example.com/data.json", name="data.json", path=tmp_path)
    assert calls[1].get("If-None-Match") == '"abc123"'


def test_fetch_raises_offline_error_with_no_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("CCAMLRGIS_CACHE_DIR", raising=False)

    def fake_get(*a, **k):
        raise cache.requests.RequestException("no network")

    monkeypatch.setattr(cache.requests, "get", fake_get)

    try:
        cache.fetch("https://example.com/nope.json", name="nope.json", path=tmp_path)
        assert False, "expected CCAMLRGISOfflineError"
    except cache.CCAMLRGISOfflineError as exc:
        assert exc.name == "nope.json"


def test_fetch_falls_back_to_cache_on_network_error(tmp_path, monkeypatch):
    monkeypatch.delenv("CCAMLRGIS_CACHE_DIR", raising=False)
    (tmp_path / "existing.json").write_bytes(b"cached")

    def fake_get(*a, **k):
        raise cache.requests.RequestException("no network")

    monkeypatch.setattr(cache.requests, "get", fake_get)

    dest = cache.fetch("https://example.com/existing.json", name="existing.json", path=tmp_path)
    assert dest.read_bytes() == b"cached"
