import json

import pytest

from ccamlrgis import load

LAYER_FNS = {
    "asds": load.load_asds,
    "ssrus": load.load_ssrus,
    "coastline": load.load_coastline,
    "rbs": load.load_rbs,
    "ssmus": load.load_ssmus,
    "mas": load.load_mas,
    "mpas": load.load_mpas,
    "eezs": load.load_eezs,
}


@pytest.mark.network
@pytest.mark.parametrize("name", sorted(LAYER_FNS))
def test_load_layer_structure_matches_r(fixtures, tmp_path, name):
    expected = json.loads((fixtures / "load_layers" / f"{name}.json").read_text())

    gdf = LAYER_FNS[name](path=tmp_path)

    assert len(gdf) > 0
    assert gdf.crs.to_epsg() == 6932
    # CCAMLR's live data can change over time (these functions fetch
    # "up-to-date" data by design -- see tools/export_r_reference.R), so
    # this checks structure, not an exact snapshot: same columns present,
    # non-empty, correctly projected.
    assert set(expected["columns"]).issubset(set(gdf.columns))
    # Rule 8: every loaded layer carries a citation.
    assert gdf.attrs.get("citation", "").startswith("CCAMLR.")
