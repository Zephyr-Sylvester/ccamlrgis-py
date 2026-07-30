import geopandas as gpd
import numpy as np
import pandas as pd

from ccamlrgis import create_hashes, create_polys


def test_create_hashes_matches_r(fixtures):
    poly_data = pd.read_csv(fixtures / "example_data" / "PolyData.csv")
    expected = gpd.read_file(fixtures / "create_hashes" / "polydata_one.gpkg")

    polys = create_polys(poly_data)
    out = create_hashes(polys.iloc[[0]], angle=45, spacing=1, width=1)

    out_area = out.geometry.iloc[0].area
    exp_area = expected.geometry.iloc[0].area
    np.testing.assert_allclose(out_area, exp_area, rtol=0.05)
