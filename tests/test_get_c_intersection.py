import json

import numpy as np

from ccamlrgis import get_c_intersection

CASES = {
    "beyond_range": ((-30, -55, -29, -50), (-50, -60, -40, -60)),
    "on_segment": ((-30, -65, -29, -50), (-50, -60, -40, -60)),
    "crossed": ((-30, -65, -29, -50), (-50, -60, -25, -60)),
    "antimeridian": ((-179, -60, -150, -50), (-120, -60, -130, -62)),
}


def test_get_c_intersection_matches_r(fixtures):
    expected = json.loads((fixtures / "get_c_intersection" / "cases.json").read_text())

    for name, (line1, line2) in CASES.items():
        result = get_c_intersection(line1, line2)
        np.testing.assert_allclose(result["Lon"], expected[name]["Lon"], rtol=1e-9)
        np.testing.assert_allclose(result["Lat"], expected[name]["Lat"], rtol=1e-9)


def test_parallel_lines_raises():
    try:
        get_c_intersection((0, -60, 10, -60), (-10, -60, 10, -60))
        assert False, "expected ValueError"
    except ValueError:
        pass
