import numpy as np
import pandas as pd
import pytest

from ccamlrgis.densify import densify_data

CASES = [
    "simple_box",
    "antimeridian_ccw",
    "antimeridian_cw",
    "exactly_180_wide",
    "iso_longitude",
    "building_polygons_P1",
    "building_polygons_P2",
    "building_polygons_P3",
]


@pytest.mark.parametrize("case", CASES)
def test_densify_matches_r(fixtures, case):
    input_df = pd.read_csv(fixtures / "densify_data" / f"{case}_input.csv")
    expected = pd.read_csv(fixtures / "densify_data" / f"{case}_output.csv")
    # R occasionally emits an exact-duplicate consecutive vertex on
    # antimeridian-crossing segments -- float noise in its own intersection
    # pipeline, not a meaningful distinct vertex (see porting_notes.md).
    # Collapse those before comparing.
    expected = expected.loc[(expected != expected.shift()).any(axis=1)].reset_index(drop=True)

    if case == "exactly_180_wide":
        with pytest.warns(UserWarning, match="exactly 180 degrees wide"):
            out = densify_data(input_df["Lon"].to_numpy(), input_df["Lat"].to_numpy())
    else:
        out = densify_data(input_df["Lon"].to_numpy(), input_df["Lat"].to_numpy())

    assert out.shape[0] == len(expected), f"{case}: expected {len(expected)} vertices, got {out.shape[0]}"
    np.testing.assert_allclose(out[:, 0], expected["Lon"], atol=1e-6)
    np.testing.assert_allclose(out[:, 1], expected["Lat"], atol=1e-6)
