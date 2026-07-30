import pytest

from ccamlrgis.cite import LAYER_INFO, layer_citation


def test_layer_citation_format():
    citation = layer_citation("asds", year=2026, version="4.2")
    assert citation == (
        "CCAMLR. (2026). Geographical data layer: Statistical Areas, Subareas and Divisions. "
        "Version 4.2, URL: https://gis.ccamlr.org/geoserver/gis/ows?service=WFS&version=1.0.0"
        "&request=GetFeature&outputFormat=json&typeName=gis:statistical_areas_6932"
    )


def test_layer_citation_case_insensitive():
    assert layer_citation("ASDs", year=2026) == layer_citation("asds", year=2026)


def test_layer_citation_defaults_version_to_year():
    citation = layer_citation("eezs", year=2020)
    assert "Version 2020" in citation


def test_layer_citation_unknown_layer_raises():
    with pytest.raises(ValueError):
        layer_citation("not_a_real_layer")


def test_all_load_functions_have_a_citation_entry():
    # every load_* key in load.py should resolve here
    for key in ("asds", "ssrus", "coastline", "rbs", "ssmus", "mas", "mpas", "eezs"):
        assert key in LAYER_INFO
        assert layer_citation(key)
