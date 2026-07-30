import pandas as pd
import pytest
import rioxarray  # noqa: F401

from ccamlrgis import create_polys, rotate_obj

# rotate_obj only re-defines a CRS (+lon_0=<lon0>) -- there's no R fixture
# to validate bit-for-bit here, just that the CRS is correctly built and
# applied to both vector and raster inputs.


def test_rotate_obj_vector(fixtures):
    poly_data = pd.read_csv(fixtures / "example_data" / "PolyData.csv")
    polys = create_polys(poly_data)

    rotated = rotate_obj(polys, lon0=-180)

    assert "lon_0=-180" in rotated.crs.to_proj4()
    assert len(rotated) == len(polys)
    assert tuple(rotated.total_bounds) != tuple(polys.total_bounds)  # actually rotated, not a no-op


def test_rotate_obj_raster(fixtures):
    bathy = rioxarray.open_rasterio(fixtures / "bathy" / "SmallBathy.tif").squeeze("band", drop=True)

    rotated = rotate_obj(bathy, lon0=-180)

    assert "lon_0=-180" in rotated.rio.crs.to_proj4()
    assert rotated.shape[0] > 0 and rotated.shape[1] > 0


def test_rotate_obj_requires_lon0():
    with pytest.raises(ValueError):
        rotate_obj(pd.DataFrame())
