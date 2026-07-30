import numpy as np
import pandas as pd

from ccamlrgis import add_colour


def _rgb(hexcode):
    h = hexcode.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _assert_colours_close(got, expected, max_channel_diff=2):
    # add_colour is explicitly cosmetic (design doc's faithfulness bar:
    # "Cosmetic plotting output need not be pixel-identical, but must be
    # visually equivalent"). R's colorRampPalette and this port's linear
    # RGB interpolation land within +/-1 per channel at rounding
    # boundaries -- invisible, not a correctness issue.
    for g, e in zip(got, expected):
        diff = max(abs(a - b) for a, b in zip(_rgb(g), _rgb(e)))
        assert diff <= max_channel_diff, f"{g} vs {e}: channel diff {diff}"


def test_add_colour_matches_r(fixtures):
    point_data = pd.read_csv(fixtures / "example_data" / "PointData.csv")
    expected_varcol = pd.read_csv(fixtures / "add_col" / "pointdata_nfishes_varcol.csv")["varcol"]
    expected_cuts = pd.read_csv(fixtures / "add_col" / "pointdata_nfishes_cuts.csv")["cuts"]
    expected_cols = pd.read_csv(fixtures / "add_col" / "pointdata_nfishes_cols.csv")["cols"]

    result = add_colour(point_data["Nfishes"].to_numpy())

    np.testing.assert_allclose(result["cuts"], expected_cuts, rtol=1e-6)
    _assert_colours_close(result["cols"], expected_cols)
    _assert_colours_close([str(c) for c in result["varcol"]], [str(c) for c in expected_varcol])
