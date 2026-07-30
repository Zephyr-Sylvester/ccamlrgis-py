import numpy as np
import pandas as pd
import pytest

from ccamlrgis import project_data


def test_forward_matches_r(fixtures):
    expected = pd.read_csv(fixtures / "project_data" / "forward.csv")
    input_df = expected[["Lat", "Lon", "id"]]

    with pytest.warns(UserWarning) as record:
        out = project_data(input_df, names_in=["Lat", "Lon"], append=True)

    messages = sorted(str(w.message) for w in record)
    expected_warnings = sorted(
        w for w in (fixtures / "project_data" / "forward_warnings.txt").read_text().split("\n\n") if w.strip()
    )
    assert [m.strip() for m in messages] == [w.strip() for w in expected_warnings]

    np.testing.assert_allclose(out["Y"], expected["Y"], rtol=1e-9)
    np.testing.assert_allclose(out["X"], expected["X"], rtol=1e-9, atol=1e-6)


def test_inverse_roundtrip_matches_r(fixtures):
    expected = pd.read_csv(fixtures / "project_data" / "inverse_roundtrip.csv")
    input_df = expected[["Y", "X"]]

    out = project_data(input_df, names_in=["Y", "X"], names_out=["Lat2", "Lon2"], append=False, inverse=True)

    np.testing.assert_allclose(out["Lat2"], expected["Lat2"], rtol=1e-9)
    np.testing.assert_allclose(out["Lon2"], expected["Lon2"], rtol=1e-9)


def test_missing_names_in_raises():
    with pytest.raises(ValueError):
        project_data(pd.DataFrame({"Lat": [1], "Lon": [2]}))
