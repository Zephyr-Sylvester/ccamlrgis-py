import geopandas as gpd
import numpy as np

from ccamlrgis import create_ellipse


def test_create_ellipse_matches_r(fixtures):
    expected = gpd.read_file(fixtures / "create_ellipse" / "example.gpkg")

    out = create_ellipse(latc=-61, lonc=-50, lmaj=500, lmin=250, ang=120)

    np.testing.assert_allclose(out.geometry.area.sum(), expected.geometry.area.sum(), rtol=1e-6)
    sym_diff = out.geometry.iloc[0].symmetric_difference(expected.geometry.iloc[0]).area
    assert sym_diff < 1e-6 * expected.geometry.area.sum()
