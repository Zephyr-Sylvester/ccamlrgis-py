import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest

from ccamlrgis import clip_to_coast


def test_clip_to_coast_matches_r(fixtures):
    input_gdf = gpd.read_file(fixtures / "clip_to_coast" / "input.gpkg")
    coast = gpd.read_file(fixtures / "clip_to_coast" / "coast_all.gpkg")
    expected = gpd.read_file(fixtures / "clip_to_coast" / "output.gpkg")

    out = clip_to_coast(input_gdf, coast)

    assert list(out["ID"]) == list(expected["ID"])
    # The exporter's fixture was built with Buffer=... applied, so add_buffer
    # already renamed AreaKm2 -> Unbuffered_AreaKm2; only
    # Buffered_and_clipped_AreaKm2 gets added here (matches R's own
    # column-presence check in Clip2Coast.R).
    assert "Clipped_AreaKm2" not in expected.columns
    np.testing.assert_allclose(out["Buffered_and_clipped_AreaKm2"], expected["Buffered_and_clipped_AreaKm2"], atol=0.1)

    sym_diff_area = out.geometry.symmetric_difference(expected.geometry).area
    np.testing.assert_allclose(sym_diff_area, 0, atol=1e-9 * out.geometry.area.sum())


@pytest.mark.network
def test_clip_to_coast_default_coast(fixtures, tmp_path, monkeypatch):
    """coast=None should default to the cache-backed bundled Coast dataset."""
    artifacts = Path(__file__).parent.parent / "data_artifacts"
    if not artifacts.exists():
        pytest.skip("data_artifacts/ not built -- run tools/build_datasets.py first")
    for f in artifacts.iterdir():
        if f.name != "manifest.json":
            shutil.copy(f, tmp_path / f.name)
    monkeypatch.setenv("CCAMLRGIS_CACHE_DIR", str(tmp_path))

    input_gdf = gpd.read_file(fixtures / "clip_to_coast" / "input.gpkg")
    out = clip_to_coast(input_gdf)

    assert "Buffered_and_clipped_AreaKm2" in out.columns
    assert len(out) == len(input_gdf)
