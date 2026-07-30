import geopandas as gpd
import numpy as np
import pandas as pd

from ccamlrgis import create_pies


def test_create_pies_matches_r(fixtures):
    pie_data = pd.read_csv(fixtures / "example_data" / "PieData.csv")
    expected = gpd.read_file(fixtures / "create_pies" / "piedata_default.gpkg")

    out = create_pies(pie_data, names_in=["Lat", "Lon", "Sp", "N"], size=50)

    assert len(out) == len(expected)
    np.testing.assert_allclose(sorted(out["p"]), sorted(expected["p"]), rtol=1e-6)
    np.testing.assert_allclose(out.geometry.area.sum(), expected.geometry.area.sum(), rtol=1e-3)
    assert set(out["Cl"]) == set(expected["Cl"])
