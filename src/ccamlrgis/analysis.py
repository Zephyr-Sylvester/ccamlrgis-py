import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer

from .crs import CCAMLR_CRS, WGS84

_FORWARD = Transformer.from_crs(WGS84, CCAMLR_CRS, always_xy=True)
_INVERSE = Transformer.from_crs(CCAMLR_CRS, WGS84, always_xy=True)


def project_data(input, names_in=None, names_out=None, append=True, inverse=False):
    """Project Lat/Lon to the CCAMLR CRS (or back-project Y/X to Lat/Lon).
    CCAMLRGIS R: project_data.r. ``names_in``/``names_out`` follow R's
    convention: [Lat-like name, Lon-like name] (Y/lat first, X/lon second).
    """
    df = pd.DataFrame(input).reset_index(drop=True)

    if names_in is None:
        raise ValueError("'names_in' not specified")
    if len(names_in) != 2:
        raise ValueError("'names_in' should be a sequence of length 2")
    if any(n not in df.columns for n in names_in):
        raise ValueError("'names_in' do not match column names in 'input'")

    if names_out is None:
        names_out = ["Latitude", "Longitude"] if inverse else ["Y", "X"]

    lat_name, lon_name = names_in[0], names_in[1]
    # locs columns: [x-like, y-like] i.e. [Lon, Lat] or [X, Y]
    locs = df[[lon_name, lat_name]].to_numpy(dtype=float, copy=True)

    missing = np.isnan(locs).any(axis=1)
    n_missing = int(missing.sum())
    if n_missing == 1:
        warnings.warn("One record is missing location and will not be projected\n")
    elif n_missing > 1:
        warnings.warn(f"{n_missing} records are missing location and will not be projected\n")

    if not inverse:
        impossible = (
            (locs[:, 0] > 180) | (locs[:, 0] < -180) | (locs[:, 1] > 90) | (locs[:, 1] < -90)
        )
        n_impossible = int(impossible.sum())
        if n_impossible == 1:
            warnings.warn("One record is not on Earth and will not be projected\n")
        elif n_impossible > 1:
            warnings.warn(f"{n_impossible} records are not on Earth and will not be projected\n")
        locs[impossible] = np.nan
    else:
        impossible = np.zeros(len(df), dtype=bool)

    fill = missing | impossible
    locs_filled = locs.copy()
    locs_filled[fill] = [0.0, -60.0]

    transformer = _INVERSE if inverse else _FORWARD
    x, y = transformer.transform(locs_filled[:, 0], locs_filled[:, 1])

    out = pd.DataFrame({names_out[1]: x, names_out[0]: y})[list(names_out)]
    out.loc[fill, :] = np.nan

    if append:
        return pd.concat([df, out], axis=1)
    return out


def clip_to_coast(input, coast):
    """Clip polygons to a coastline, removing the land portion, and record
    the resulting area. CCAMLRGIS R: Clip2Coast.R.

    Unlike R (which defaults to a bundled low-res ``Coast`` dataset),
    ``coast`` must be supplied explicitly for now -- e.g. the output of
    ``load_coastline()`` -- since that bundled dataset isn't hosted yet via
    the cache pipeline (see porting_notes.md). ``coast`` may be any
    GeoDataFrame/GeoSeries of land polygons; all of its geometries are
    unioned before differencing.
    """
    land = coast.geometry.union_all() if hasattr(coast, "geometry") else coast.union_all()
    output = input.copy()
    output["geometry"] = output.geometry.difference(land)
    area = (output.geometry.area / 1_000_000).round(1)
    if "Buffered_AreaKm2" in output.columns:
        output["Buffered_and_clipped_AreaKm2"] = area
    if "AreaKm2" in output.columns:
        output["Clipped_AreaKm2"] = area
    return output


def assign_areas(input, polys, area_name_format="GAR_Long_Label", buffer=0, names_in=None, names_out=None):
    """Assign point locations to whichever polygon(s) they fall in (e.g.
    which ASD/SSRU a fishing location occurred in). CCAMLRGIS R:
    assign_areas.r.

    Deviation from R: R's ``Polys`` is a character vector naming objects
    pre-loaded in the *caller's* global environment, looked up via ``get()``
    -- there's no safe Python equivalent. ``polys`` here is a dict mapping
    those same names directly to GeoDataFrames, e.g.
    ``polys={"ASDs": load_asds(), "SSRUs": load_ssrus()}`` (porting_notes.md
    deviation 9). ``names_out`` defaults to ``list(polys)`` (R: ``Polys``).
    """
    df = pd.DataFrame(input).reset_index(drop=True)

    if names_in is not None:
        if len(names_in) != 2:
            raise ValueError("'names_in' should be a sequence of length 2")
        if any(n not in df.columns for n in names_in):
            raise ValueError("'names_in' do not match column names in 'input'")

    poly_names = list(polys.keys())
    if names_out is None:
        names_out = poly_names
    if any(n in df.columns for n in names_out):
        raise ValueError("'names_out' matches column names in 'input', please use different names")

    buffer_arr = np.atleast_1d(buffer).astype(float)
    buffer_list = [buffer_arr[0]] * len(poly_names) if len(buffer_arr) == 1 else list(buffer_arr)
    fmt_list = [area_name_format] * len(poly_names) if isinstance(area_name_format, str) else list(area_name_format)

    lat_col, lon_col = (names_in[0], names_in[1]) if names_in else (df.columns[0], df.columns[1])
    locs = df[[lon_col, lat_col]].to_numpy(dtype=float)

    missing = np.isnan(locs).any(axis=1)
    n_missing = int(missing.sum())
    if n_missing == 1:
        warnings.warn("One record is missing location and will not be assigned to any area.")
    elif n_missing > 1:
        warnings.warn(f"{n_missing} records are missing location and will not be assigned to any area.")

    impossible = (locs[:, 0] > 180) | (locs[:, 0] < -180) | (locs[:, 1] > 90) | (locs[:, 1] < -90)
    n_impossible = int(impossible.sum())
    if n_impossible == 1:
        warnings.warn("One record is not on Earth and will not be assigned to any area.")
    elif n_impossible > 1:
        warnings.warn(f"{n_impossible} records are not on Earth and will not be assigned to any area.")
    locs = locs.copy()
    locs[impossible] = np.nan

    valid = ~np.isnan(locs).any(axis=1)
    unique_locs = np.unique(locs[valid], axis=0)  # deduped [lon, lat] rows

    points = gpd.GeoSeries(gpd.points_from_xy(unique_locs[:, 0], unique_locs[:, 1]), crs=WGS84).to_crs(CCAMLR_CRS)

    assigned = pd.DataFrame({"Lat": unique_locs[:, 1], "Lon": unique_locs[:, 0]})
    for name, out_name, buf, fmt in zip(poly_names, names_out, buffer_list, fmt_list):
        area_gdf = polys[name]
        if buf > 0:
            area_gdf = area_gdf.copy()
            area_gdf["geometry"] = area_gdf.geometry.buffer(buf * 1852)

        sindex = area_gdf.sindex
        sindex_1m = area_gdf.geometry.buffer(1).sindex
        match_idx = np.full(len(points), np.nan)
        match2_idx = np.full(len(points), np.nan)
        for i, geom in enumerate(points):
            cand = sindex.query(geom, predicate="intersects")
            if len(cand):
                match_idx[i] = cand.min()
            cand2 = sindex_1m.query(geom, predicate="intersects")
            if len(cand2):
                match2_idx[i] = cand2.min()
        if not np.array_equal(np.nan_to_num(match_idx, nan=-1), np.nan_to_num(match2_idx, nan=-1)):
            warnings.warn(
                "Some record(s) might be exactly on the edge of the area of interest and will not be assigned to it."
            )

        values = area_gdf[fmt].astype(str).to_numpy()
        out_col = np.full(len(points), None, dtype=object)
        has_match = ~np.isnan(match_idx)
        out_col[has_match] = values[match_idx[has_match].astype(int)]
        assigned[out_name] = out_col

    merged = df.merge(assigned.rename(columns={"Lat": lat_col, "Lon": lon_col}), on=[lat_col, lon_col], how="left")
    return merged


def rotate_obj(input, lon0=None):
    """Rotate a vector or raster object by re-defining its projection so
    that ``lon0`` points up. For plotting only, not analysis -- distances
    and areas computed after rotation are not meaningful. CCAMLRGIS R:
    Rotate_obj.R.
    """
    if lon0 is None:
        raise ValueError("'lon0' must be numeric.")
    crs_to = f"+proj=laea +lat_0=-90 +lon_0={lon0} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    if isinstance(input, (gpd.GeoDataFrame, gpd.GeoSeries)):
        return input.to_crs(crs_to)
    if hasattr(input, "rio"):
        return input.rio.reproject(crs_to)
    raise TypeError("'input' must be a GeoDataFrame/GeoSeries or an xarray.DataArray raster (with a .rio accessor).")


def get_c_intersection(line1, line2):
    """Cartesian (planar, not geodesic) intersection of two lines each
    given as ``[lon_start, lat_start, lon_end, lat_end]``. CCAMLRGIS R:
    get_C_intersection.R (formula:
    https://en.wikipedia.org/wiki/Line-line_intersection).

    Deviation: ``Plot=`` is dropped -- Python never draws as a side effect
    (design doc section 1.2); use a separate plot helper if a diagram of
    the intersection is wanted.
    """
    x1, y1, x2, y2 = line1
    x3, y3, x4, y4 = line2
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if d == 0:
        raise ValueError("Parallel lines.")
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / d
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / d
    if abs(px) > 180:
        warnings.warn(
            "Antimeridian crossed. Find where your line crosses it first, "
            "using line=[180,-90,180,0] or line=[-180,-90,-180,0]."
        )
    return {"Lon": px, "Lat": py}


def get_depths(input, bathy, names_in=None):
    """Sample a bathymetry raster's depth at point locations (nearest-cell
    value, no interpolation -- matches terra::extract's default). CCAMLRGIS
    R: get_depths.R.
    """
    df = pd.DataFrame(input).copy()
    if names_in is None:
        names_in = list(df.columns[:2])
    elif len(names_in) != 2:
        raise ValueError("'names_in' should be a sequence of length 2")
    elif any(n not in df.columns for n in names_in):
        raise ValueError("'names_in' do not match column names in 'input'")

    xy = project_data(df, names_in=names_in, append=False)
    x = xr.DataArray(xy["X"].to_numpy(), dims="points")
    y = xr.DataArray(xy["Y"].to_numpy(), dims="points")
    depths = bathy.sel(x=x, y=y, method="nearest").to_numpy()

    out = df.copy()
    out["d"] = depths
    return out


def seabed_area(bathy, poly, poly_names=None, depth_classes=(-600, -1800)):
    """Planimetric seabed area within polygons and depth strata, in km2.
    CCAMLRGIS R: seabed_area.R.
    """
    if poly_names is None:
        raise ValueError("'poly_names' is missing")
    if poly_names not in poly.columns:
        raise ValueError("'poly_names' does not match column names in 'poly'")

    px_w, px_h = bathy.rio.resolution()
    pixel_area_km2 = abs(px_w * px_h) / 1_000_000

    pairs = list(zip(depth_classes[:-1], depth_classes[1:]))
    col_names = [f"{a}|{b}" for a, b in pairs]

    rows = []
    for _, row in poly.iterrows():
        # all_touched=True matches terra::mask()'s default (any overlap
        # counts, not just cell-centre-in-polygon) -- confirmed against the
        # G3 fixture: all_touched=False undercounted every non-trivial
        # stratum (e.g. 189 vs R's 196 cells on the "one" polygon's
        # -200|-600 stratum).
        clipped = bathy.rio.clip([row.geometry], poly.crs, drop=True, invert=False, all_touched=True)
        arr = clipped.to_numpy()
        result = {poly_names: str(row[poly_names])}
        for (dtop, dbot), name in zip(pairs, col_names):
            # terra::classify's two-step masking keeps the OPEN interval
            # (dbot, dtop) -- strictly between the strata bounds.
            in_range = (arr > dbot) & (arr < dtop)
            result[name] = round(float(np.count_nonzero(in_range)) * pixel_area_km2, 2)
        rows.append(result)

    out = pd.DataFrame(rows)
    if "-600|-1800" in out.columns:
        out = out.rename(columns={"-600|-1800": "Fishable_area"})
    return out


def get_iso_polys(rast, poly=None, cuts=None, cols=("green", "yellow", "red"), grp=False, strict=True):
    """Turn a raster into filled contour-band polygons between `cuts`.
    CCAMLRGIS R: get_iso_polys.R.

    Deviation: R uses the `isoband` package, which linearly interpolates
    band boundaries between cell centres (smooth contours). This port uses
    `rasterio.features.shapes` on a classified array instead (design doc's
    other suggested option) -- boundaries follow raster cell edges (blocky)
    rather than being interpolated. No new dependency, and area per band
    should still closely match R's at typical bathymetry resolutions; see
    porting_notes.md for the fixture-validated area comparison.
    """
    import rasterio.features
    from shapely.geometry import shape as shapely_shape

    if poly is not None:
        geom = poly.geometry.union_all() if hasattr(poly, "geometry") else poly.union_all()
        # Unlike seabed_area's per-stratum masking (all_touched=True matches
        # terra::mask() there), the initial Poly clip here matches R almost
        # exactly with all_touched=False (0.01% total-area difference vs
        # ~6.7% with True) -- confirmed against the G3 fixture. The two
        # functions' clip calls aren't equivalent enough to share one rule;
        # each was calibrated against its own fixture.
        rast = rast.rio.clip([geom], poly.crs, drop=True, all_touched=False)

    cuts_full = np.concatenate([[-np.inf], np.sort(np.asarray(cuts, dtype=float)), [np.inf]])
    lo, hi = cuts_full[:-1], cuts_full[1:]

    arr = rast.to_numpy()
    valid = np.isfinite(arr)
    band_idx = np.digitize(arr, cuts_full[1:-1], right=False)  # right=False: bins are [lo, hi)

    transform = rast.rio.transform()
    records = []
    for i in range(len(lo)):
        mask = valid & (band_idx == i)
        if not mask.any():
            continue
        for geom_json, _ in rasterio.features.shapes(mask.astype(np.uint8), mask=mask, transform=transform):
            records.append({"Min": lo[i], "Max": hi[i], "geometry": shapely_shape(geom_json)})

    cs = gpd.GeoDataFrame(records, crs=rast.rio.crs)
    if strict:
        cs = cs[np.isfinite(cs["Min"]) & np.isfinite(cs["Max"])].reset_index(drop=True)

    iso_map = {m: i + 1 for i, m in enumerate(sorted(cs["Min"].unique()))}
    cs["Iso"] = cs["Min"].map(iso_map)
    from .colours import add_colour

    cs["c"] = add_colour(cs["Iso"].to_numpy(), cuts=100, cols=cols)["varcol"]
    cs["ID"] = np.arange(1, len(cs) + 1)

    if grp:
        cs = cs.reset_index(drop=True)
        touches = [cs.geometry.iloc[i:].index[cs.geometry.iloc[i:].touches(cs.geometry.iloc[i])].tolist() for i in range(len(cs))]
        group = np.full(len(cs), np.nan)
        group[0] = 1
        for i in range(1, len(cs)):
            neighbours = [j for j in touches[i] if j != i]
            if not neighbours:
                group[i] = group[i - 1] + 1
            elif np.isnan(group[i]):
                idx = [i] + neighbours
                group[np.array(idx)] = group[i - 1] + 1
        cs["Grp"] = group.astype(int)
        cs["AreaKm2"] = (cs.geometry.area / 1_000_000).round(2)
        centroids = cs.geometry.centroid
        cs["Labx"] = centroids.x
        cs["Laby"] = centroids.y
        # keep the label only on the deepest (max Iso) polygon per group
        keep = cs.groupby("Grp")["Iso"].transform("max") == cs["Iso"]
        cs.loc[~keep, ["Labx", "Laby"]] = np.nan
        cs["ID"] = np.arange(1, len(cs) + 1)

    return cs.reset_index(drop=True)
