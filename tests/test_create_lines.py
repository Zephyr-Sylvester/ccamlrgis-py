import geopandas as gpd
import pandas as pd
from conftest import assert_geom_equal

from ccamlrgis import create_lines


def test_linedata_densify_matches_r(fixtures):
    line_data = pd.read_csv(fixtures / "example_data" / "LineData.csv")
    expected = gpd.read_file(fixtures / "create_lines" / "linedata_densify.gpkg")

    out = create_lines(line_data, densify=True)

    assert_geom_equal(out, expected)
