import pandas as pd
import pytest

from ccamlrgis import assign_areas, load_asds, load_ssrus


@pytest.mark.network
def test_assign_areas_matches_r(fixtures):
    expected = pd.read_csv(fixtures / "assign_areas" / "fixed_points.csv")
    input_df = expected[["Lat", "Lon"]]

    asds = load_asds()
    ssrus = load_ssrus()

    out = assign_areas(input_df, polys={"ASDs": asds, "SSRUs": ssrus}, names_out=["ASD", "SSRU"])

    assert list(out["ASD"].astype("string")) == list(expected["ASD"].astype("string"))
    assert list(out["SSRU"].astype("string")) == list(expected["SSRU"].astype("string"))
