import geopandas as gpd
import numpy as np
import pandas as pd

from ccamlrgis import create_arrow


def test_create_arrow_example1_straight(fixtures):
    expected = gpd.read_file(fixtures / "create_arrow" / "example1_straight.gpkg")
    input_df = pd.DataFrame({"lat": [-61, -52], "lon": [-60, -40]})

    out = create_arrow(input_df)

    np.testing.assert_allclose(out.geometry.area.sum(), expected.geometry.area.sum(), rtol=0.05)


def test_create_arrow_example2_bend(fixtures):
    expected = gpd.read_file(fixtures / "create_arrow" / "example2_bend.gpkg")
    input_df = pd.DataFrame({"lat": [-61, -65, -52], "lon": [-60, -45, -40]})

    out = create_arrow(input_df, colour="lightblue")

    np.testing.assert_allclose(out.geometry.area.sum(), expected.geometry.area.sum(), rtol=0.05)


def test_create_arrow_example4_weighted(fixtures):
    expected = gpd.read_file(fixtures / "create_arrow" / "example4_weighted.gpkg")
    input_df = pd.DataFrame({"lat": [-61, -60, -65, -52], "lon": [-60, -50, -45, -40], "w": [1, 1, 2, 1]})

    out = create_arrow(input_df, colour="lightblue", hlength=20, hwidth=20)

    np.testing.assert_allclose(out.geometry.area.sum(), expected.geometry.area.sum(), rtol=0.05)
