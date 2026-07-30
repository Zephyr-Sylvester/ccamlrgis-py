import geopandas as gpd
import numpy as np
import pandas as pd
import rioxarray

from ccamlrgis import create_polys, get_iso_polys


def test_get_iso_polys_matches_r(fixtures):
    expected = gpd.read_file(fixtures / "get_iso_polys" / "smallbathy_example.gpkg")
    bathy = rioxarray.open_rasterio(fixtures / "bathy" / "SmallBathy.tif").squeeze("band", drop=True)

    poly = create_polys(pd.DataFrame({"ID": 1, "Lat": [-55, -55, -61, -61], "Lon": [-30, -25, -25, -30]}))
    cuts = np.linspace(-8000, 0, 10)

    out = get_iso_polys(bathy, poly=poly, cuts=cuts)

    # This port uses raster-cell-boundary polygons (rasterio.features.shapes
    # on a classified array) rather than R's isoband-interpolated smooth
    # contours -- see porting_notes.md deviation 12. Compare per-band
    # (Min,Max) total area rather than per-polygon-row alignment, since band
    # fragmentation into individual polygons can differ between the two
    # approaches even when total covered area per band is the same.
    out_area = out.groupby(["Min", "Max"])["geometry"].apply(lambda g: g.area.sum() / 1_000_000)
    exp_area = expected.groupby(["Min", "Max"])["geometry"].apply(lambda g: g.area.sum() / 1_000_000)
    assert set(out_area.index) == set(exp_area.index)

    # Total covered area: tight tolerance, this should be near-exact.
    np.testing.assert_allclose(out_area.sum(), exp_area.sum(), rtol=0.01)

    # Per-band: loose tolerance. Confirmed against this fixture that most
    # bands land within a few percent, but thin bands abutting a boundary
    # (coastline, or the shallowest/deepest cut) can diverge by up to ~25%
    # -- exactly where blocky vs. interpolated contours differ most. A
    # human glancing at the two maps would still call them equivalent.
    for key in exp_area.index:
        np.testing.assert_allclose(out_area[key], exp_area[key], atol=max(500, 0.3 * exp_area[key]))
