import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio.features
from shapely.geometry import shape as shapely_shape
from shapely.ops import unary_union

from .analysis import project_data
from .crs import CCAMLR_CRS


def _stratum_polygon(arr, transform, top, bot):
    """Vectorise the raster cells with top <= value <= bot into a polygon.
    Same raster-cell-boundary (blocky) approach as get_iso_polys -- see
    porting_notes.md deviation 12.
    """
    mask = np.isfinite(arr) & (arr >= top) & (arr <= bot)
    if not mask.any():
        return None
    geoms = [
        shapely_shape(g) for g, _ in rasterio.features.shapes(mask.astype(np.uint8), mask=mask, transform=transform)
    ]
    return unary_union(geoms)


def create_stations(poly, bathy, depths, n=None, n_auto=None, dist=None, buf=1000, rng=None, seed=None):
    """Random (or minimum-spaced) station locations inside a polygon,
    stratified by depth range. CCAMLRGIS R: create_Stations (create.R).

    Deviation: R has no seeding -- station picking uses R's global RNG.
    `rng=`/`seed=` are Python-only additions (design doc's own plan) so
    results are reproducible; pass a `numpy.random.Generator` via `rng=`
    or an int via `seed=`.
    """
    if n is not None and n_auto is not None:
        raise ValueError("Values should not be specified for both n and n_auto.")
    depths = list(depths)
    n_strata = len(depths) - 1
    if n is not None and len(n) != n_strata:
        raise ValueError("Incorrect number of stations specified.")

    rng = rng if rng is not None else np.random.default_rng(seed)

    minx, miny, maxx, maxy = poly.total_bounds
    bathy_c = bathy.rio.clip_box(minx=minx - 10000, miny=miny - 10000, maxx=maxx + 10000, maxy=maxy + 10000)
    transform = bathy_c.rio.transform()
    arr = bathy_c.to_numpy()

    tops, bots = depths[:-1], depths[1:]
    stratum_names = [f"{abs(t)}-{abs(b)}" for t, b in zip(tops, bots)]

    poly_geom = poly.geometry.union_all()
    strata = [_stratum_polygon(arr, transform, top, bot) for top, bot in zip(tops, bots)]
    strata = [s.intersection(poly_geom) if s is not None else None for s in strata]

    areas = np.array([s.area if s is not None else 0.0 for s in strata])
    counts = np.round(areas / areas.max() * n_auto).astype(int) if n_auto is not None else np.asarray(n, dtype=int)

    valid = [s for s in strata if s is not None and not s.is_empty]
    if not valid:
        raise ValueError("No valid depth strata found within the polygon.")
    gminx, gminy, gmaxx, gmaxy = unary_union(valid).bounds
    xs = np.arange(gminx, gmaxx, 1000)
    ys = np.arange(gminy, gmaxy, 1000)
    gx, gy = np.meshgrid(xs, ys)
    grid_x, grid_y = gx.ravel(), gy.ravel()
    grid_points = gpd.GeoSeries(gpd.points_from_xy(grid_x, grid_y), crs=CCAMLR_CRS)

    rows = []
    for i, s in enumerate(strata):
        if s is None or s.is_empty:
            continue
        eroded = s.buffer(-buf)
        if eroded.is_empty:
            continue
        inside = grid_points.within(eroded)
        idx = np.flatnonzero(inside.to_numpy())
        for j in idx:
            rows.append((grid_x[j], grid_y[j], i))
    candidates = pd.DataFrame(rows, columns=["x", "y", "stratum"])

    if dist is None:
        picked = []
        for i in range(n_strata):
            sub = candidates[candidates["stratum"] == i]
            idx = rng.choice(sub.index.to_numpy(), size=counts[i], replace=False)
            picked.append(sub.loc[idx])
        stations = pd.concat(picked, ignore_index=True) if picked else candidates.iloc[0:0]
    else:
        width = 100 * np.ceil(1852 * dist / 100)
        remaining = candidates.reset_index(drop=True)
        kept_rows = []
        first = True
        while len(remaining) > 0:
            idx = len(remaining) // 2 if first else rng.integers(0, len(remaining))
            first = False
            row = remaining.iloc[idx]
            kept_rows.append(row)
            d = np.hypot(remaining["x"].to_numpy() - row["x"], remaining["y"].to_numpy() - row["y"])
            remaining = remaining[d > width].reset_index(drop=True)
        # each row in kept_rows is a single-dtype pandas Series (mixing the
        # float x/y columns with the int stratum column upcasts stratum to
        # float) -- restore it explicitly.
        kept = pd.DataFrame(kept_rows).reset_index(drop=True)
        kept["stratum"] = kept["stratum"].astype(int)
        for i in range(n_strata):
            if (kept["stratum"] == i).sum() < counts[i]:
                raise ValueError(
                    "Cannot generate stations given the constraints. Reduce dist and/or number of stations and/or buf."
                )
        picked = []
        for i in range(n_strata):
            sub = kept[kept["stratum"] == i]
            idx = rng.choice(sub.index.to_numpy(), size=counts[i], replace=False)
            picked.append(sub.loc[idx])
        stations = pd.concat(picked, ignore_index=True)

    stations["Stratum"] = [stratum_names[i] for i in stations["stratum"]]
    stations = stations.rename(columns={"x": "X", "y": "Y"})
    stations = project_data(stations, names_in=["Y", "X"], names_out=["Lat", "Lon"], append=True, inverse=True)
    return gpd.GeoDataFrame(stations, geometry=gpd.points_from_xy(stations["X"], stations["Y"]), crs=CCAMLR_CRS)
