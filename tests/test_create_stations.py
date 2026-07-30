import geopandas as gpd
import numpy as np
import pytest
import rioxarray  # noqa: F401

from ccamlrgis import create_stations

DEPTHS = (-2000, -1500, -1000, -550)
SEEDS = range(15)


@pytest.fixture
def station_inputs(fixtures):
    poly = gpd.read_file(fixtures / "create_stations" / "input_poly.gpkg")
    bathy = rioxarray.open_rasterio(fixtures / "bathy" / "SmallBathy.tif").squeeze("band", drop=True)
    return poly, bathy


def test_nauto_counts_close_to_r(fixtures, station_inputs):
    """Sanity-checks area-proportional station counts (round(area/max(area)
    * n_auto)) against a single R reference run -- not a distributional
    match (station picking is random in both languages and not
    reproducible across them). See porting_notes.md.
    """
    import pandas as pd

    poly, bathy = station_inputs
    expected = pd.read_csv(fixtures / "create_stations" / "nauto_counts.csv")
    expected_by_stratum = dict(zip(expected["Stratum"], expected["Count"]))

    out = create_stations(poly, bathy, DEPTHS, n_auto=20, seed=1)
    got_by_stratum = out["Stratum"].value_counts().to_dict()

    assert set(got_by_stratum) == set(expected_by_stratum)
    for stratum, exp_count in expected_by_stratum.items():
        np.testing.assert_allclose(got_by_stratum[stratum], exp_count, atol=2)


@pytest.mark.parametrize("seed", SEEDS)
def test_stations_respect_invariants(station_inputs, seed):
    """Every run, regardless of seed, must produce stations that are
    inside the input polygon and labelled with a valid stratum -- these
    are the properties that matter, not exact placement.
    """
    poly, bathy = station_inputs
    out = create_stations(poly, bathy, DEPTHS, n=[5, 5, 5], seed=seed)

    assert len(out) == 15
    poly_geom = poly.geometry.union_all()
    assert out.geometry.within(poly_geom.buffer(1)).all()  # buffer(1): tolerate the erosion boundary's own precision
    assert set(out["Stratum"]) <= {"2000-1500", "1500-1000", "1000-550"}
    assert (out["Stratum"].value_counts() == 5).all()


@pytest.mark.parametrize("seed", SEEDS)
def test_stations_respect_min_distance(station_inputs, seed):
    poly, bathy = station_inputs
    dist_nm = 3
    out = create_stations(poly, bathy, DEPTHS, n=[3, 3, 3], dist=dist_nm, seed=seed)

    coords = np.column_stack([out.geometry.x, out.geometry.y])
    min_sep_m = dist_nm * 1852
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            sep = np.hypot(*(coords[i] - coords[j]))
            assert sep >= min_sep_m * 0.99  # small float-tolerance margin
