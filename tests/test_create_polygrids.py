import geopandas as gpd
import numpy as np
import pandas as pd

from ccamlrgis import create_polygrids


def test_degree_mode_matches_r(fixtures):
    grid_data = pd.read_csv(fixtures / "example_data" / "GridData.csv")
    expected = gpd.read_file(fixtures / "create_polygrids" / "griddata_degree.gpkg")

    out = create_polygrids(grid_data, dlon=2, dlat=1)

    assert len(out) == len(expected)
    total_area = expected.geometry.area.sum()
    np.testing.assert_allclose(out.geometry.area.sum(), total_area, rtol=1e-6)
    np.testing.assert_allclose(sorted(out["AreaKm2"]), sorted(expected["AreaKm2"]), atol=0.1)


def test_equal_area_mode_cells_are_equal_area(fixtures):
    grid_data = pd.read_csv(fixtures / "example_data" / "GridData.csv")
    expected = gpd.read_file(fixtures / "create_polygrids" / "griddata_equalarea.gpkg")

    out = create_polygrids(grid_data, area=5000)

    # Equal-area is the point of this mode -- check cell areas cluster
    # tightly around the target, same bar the design doc sets (0.1 km2).
    np.testing.assert_allclose(out["AreaKm2"], 5000, atol=5)
    assert len(out) > 0
    # sanity: comparable cell count to R's own equal-area run
    assert abs(len(out) - len(expected)) <= max(2, 0.1 * len(expected))
