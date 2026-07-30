import geopandas as gpd
import numpy as np

from ccamlrgis import create_circular_arrow


def test_create_circular_arrow_default(fixtures):
    expected = gpd.read_file(fixtures / "create_circular_arrow" / "default.gpkg")

    out = create_circular_arrow()

    np.testing.assert_allclose(out.geometry.area.sum(), expected.geometry.area.sum(), rtol=0.05)
