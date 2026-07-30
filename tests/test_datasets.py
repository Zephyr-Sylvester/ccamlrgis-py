"""Tests the cache/fetch/fallback path end-to-end using tools/build_datasets.py's
real output as a pre-populated cache. Marked network: even though these
never need real release assets to exist yet (a 404 falls back to the
pre-populated file, exactly as it will once published), fetching still
means one real HTTP round-trip per dataset.
"""

import shutil

import pytest

from ccamlrgis import datasets, small_bathy

TABULAR = ("PolyData", "GridData", "PointData", "LineData", "PieData", "PieData2", "Labels")


@pytest.fixture
def populated_cache(tmp_path):
    artifacts = shutil_artifacts_dir()
    if not artifacts.exists():
        pytest.skip("data_artifacts/ not built -- run tools/build_datasets.py first")
    for f in artifacts.iterdir():
        if f.name != "manifest.json":
            shutil.copy(f, tmp_path / f.name)
    return tmp_path


def shutil_artifacts_dir():
    from pathlib import Path

    return Path(__file__).parent.parent / "data_artifacts"


@pytest.mark.network
@pytest.mark.parametrize("name", TABULAR)
def test_load_example_tabular(populated_cache, name):
    df = datasets.load_example(name, path=populated_cache)
    assert len(df) > 0


@pytest.mark.network
def test_load_example_coast(populated_cache):
    coast = datasets.load_example("Coast", path=populated_cache)
    assert len(coast) > 0
    assert coast.crs.to_epsg() == 6932


@pytest.mark.network
def test_small_bathy(populated_cache):
    bathy = small_bathy(path=populated_cache)
    assert bathy.rio.crs.to_epsg() == 6932
    assert bathy.shape[0] > 0


def test_load_example_unknown_name_raises():
    with pytest.raises(ValueError):
        datasets.load_example("NotARealDataset")
