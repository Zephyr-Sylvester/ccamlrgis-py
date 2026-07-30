import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
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
