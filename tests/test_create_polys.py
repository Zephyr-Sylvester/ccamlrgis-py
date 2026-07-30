import geopandas as gpd
import pandas as pd
from conftest import assert_geom_equal

from ccamlrgis import create_polys


def test_polydata_default_matches_r(fixtures):
    poly_data = pd.read_csv(fixtures / "example_data" / "PolyData.csv")
    expected = gpd.read_file(fixtures / "create_polys" / "polydata_default.gpkg")

    out = create_polys(poly_data)

    assert_geom_equal(out, expected)


def test_building_polygons_matches_r(fixtures):
    bp = pd.read_csv(fixtures / "building_polygons" / "My_Polygons_Form.csv")
    expected = gpd.read_file(fixtures / "create_polys" / "building_polygons.gpkg")

    out = create_polys(bp)

    assert_geom_equal(out, expected)


def test_buffered_matches_clip_to_coast_input_fixture(fixtures):
    # tests/fixtures/clip_to_coast/input.gpkg is exactly
    # create_Polys(PolyData, Densify=TRUE, Buffer=c(10,-15,120)) -- reused
    # here rather than duplicating a buffered-case fixture.
    poly_data = pd.read_csv(fixtures / "example_data" / "PolyData.csv")
    expected = gpd.read_file(fixtures / "clip_to_coast" / "input.gpkg")

    out = create_polys(poly_data, buffer=[10, -15, 120])

    assert_geom_equal(out, expected)
