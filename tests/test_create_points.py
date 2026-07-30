import geopandas as gpd
import pandas as pd
from conftest import assert_geom_equal

from ccamlrgis import create_points


def test_pointdata_matches_r(fixtures):
    point_data = pd.read_csv(fixtures / "example_data" / "PointData.csv")
    expected = gpd.read_file(fixtures / "create_points" / "pointdata.gpkg")

    out = create_points(point_data)

    assert_geom_equal(out, expected)
