#!/usr/bin/env python3
"""Builds the downloadable data artifacts (design doc section 4) that
ccamlrgis.datasets/small_bathy fetch on demand. These are published as a
GitHub Release asset set, versioned independently of the code -- nothing
is bundled in the wheel. Run from the repo root:

    conda run -n ccamlrgis-py python tools/build_datasets.py

Requires the `rdata` package (reads most of data/*.RData without needing
R at all) and, for one dataset, Rscript with CCAMLRGIS installed: `rdata`
cannot properly reconstruct `Coast` (an sf object) -- confirmed
empirically, it warns about missing bbox/crs/XY/MULTIPOLYGON/sfg/sfc/sf
constructors and falls back to raw coordinate arrays with no CRS -- so
that one dataset uses the R fallback the design doc allows for exactly
this case. Everything else here is pure Python.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import rdata

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_R_SOURCE_DIR = REPO_ROOT.parent / "CCAMLRGIS-master"

TABULAR_DATASETS = ("PolyData", "GridData", "PointData", "LineData", "PieData", "PieData2", "Labels")


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(manifest, path):
    manifest[path.name] = {"sha256": _sha256(path), "bytes": path.stat().st_size}


def build(output_dir, r_source_dir, r_env="ccamlrgis-r"):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = r_source_dir / "data"
    bathy_tif = r_source_dir / "inst" / "extdata" / "SmallBathy.tif"
    manifest = {}

    for name in TABULAR_DATASETS:
        rda_path = data_dir / f"{name}.RData"
        df = rdata.read_rda(rda_path)[name]
        out_path = output_dir / f"{name}.csv"
        df.to_csv(out_path, index=False)
        _record(manifest, out_path)
        print(f"wrote {out_path.name} ({df.shape[0]} rows)")

    coast_path = output_dir / "Coast.gpkg"
    r_script = (
        f'library(CCAMLRGIS); '
        f'sf::st_write(Coast, "{coast_path}", quiet=TRUE, append=FALSE, delete_dsn=TRUE)'
    )
    subprocess.run(["conda", "run", "-n", r_env, "Rscript", "-e", r_script], check=True)
    _record(manifest, coast_path)
    print(f"wrote {coast_path.name} (R fallback: rdata can't reconstruct sf geometry/CRS)")

    bathy_out = output_dir / "SmallBathy.tif"
    shutil.copy(bathy_tif, bathy_out)
    _record(manifest, bathy_out)
    print(f"wrote {bathy_out.name}")

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"wrote {manifest_path.name}")

    total_bytes = sum(m["bytes"] for m in manifest.values())
    print(f"\n{len(manifest)} files, {total_bytes / 1024:.1f} KB total, in {output_dir}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=REPO_ROOT / "data_artifacts")
    parser.add_argument("--r-source-dir", default=DEFAULT_R_SOURCE_DIR, help="Path to the CCAMLRGIS R package checkout (contains data/ and inst/extdata/)")
    parser.add_argument("--r-env", default="ccamlrgis-r", help="Conda env name with CCAMLRGIS installed")
    args = parser.parse_args()
    build(Path(args.output_dir), Path(args.r_source_dir), args.r_env)
