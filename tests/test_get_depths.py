import numpy as np
import pandas as pd
import rioxarray

from ccamlrgis import get_depths


def test_get_depths_matches_r(fixtures):
    point_data = pd.read_csv(fixtures / "example_data" / "PointData.csv")
    expected = pd.read_csv(fixtures / "get_depths" / "pointdata_depths.csv")
    bathy = rioxarray.open_rasterio(fixtures / "bathy" / "SmallBathy.tif").squeeze("band", drop=True)

    input_df = pd.DataFrame({"Lat": point_data["Lat"], "Lon": point_data["Lon"], "Catch": point_data["Catch"]})
    out = get_depths(input_df, bathy)

    np.testing.assert_allclose(out["d"], expected["d"], rtol=1e-6)
