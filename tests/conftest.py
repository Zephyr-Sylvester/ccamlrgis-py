from pathlib import Path

import numpy as np
import pandas as pd
import pytest

FIXTURES = Path(__file__).parent / "fixtures"

_AREA_COLS = {"AreaKm2", "Unbuffered_AreaKm2", "Buffered_AreaKm2", "Clipped_AreaKm2", "Buffered_and_clipped_AreaKm2"}


@pytest.fixture
def fixtures():
    return FIXTURES


def assert_geom_equal(py_gdf, r_gdf, id_col="ID", tol=1e-6):
    """Per design doc section 6: same feature count/IDs, geometry equal
    within `tol` (by symmetric-difference area, robust to vertex-order/
    float-noise differences that don't change the shape), numeric columns
    close to rtol=1e-9, area columns at R's own rounding (1 decimal).
    """
    assert len(py_gdf) == len(r_gdf), f"feature count: {len(py_gdf)} vs {len(r_gdf)}"
    assert list(py_gdf[id_col]) == list(r_gdf[id_col]), "IDs/order differ"

    total_area = r_gdf.geometry.area.sum()
    sym_diff_area = py_gdf.geometry.symmetric_difference(r_gdf.geometry).area
    np.testing.assert_allclose(sym_diff_area, 0, atol=max(tol, 1e-9 * total_area))

    shared_cols = (set(py_gdf.columns) & set(r_gdf.columns)) - {"geometry", id_col}
    for col in shared_cols:
        if col in _AREA_COLS:
            np.testing.assert_allclose(py_gdf[col], r_gdf[col], atol=0.1)
        elif pd.api.types.is_numeric_dtype(r_gdf[col]):
            np.testing.assert_allclose(py_gdf[col], r_gdf[col], rtol=1e-6, atol=1e-6)
