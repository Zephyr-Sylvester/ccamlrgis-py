import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon

from .analysis import clip_to_coast, project_data
from .colours import add_colour
from .crs import CCAMLR_CRS, WGS84
from .densify import densify_data

_STATS = ["min", "max", "mean", "sum", "count", "sd", "median"]
_FORWARD = Transformer.from_crs(WGS84, CCAMLR_CRS, always_xy=True)


def _reorder_columns(df, names_in, expected_len):
    if names_in is None:
        return df
    if len(names_in) != expected_len:
        raise ValueError(f"'names_in' should be a sequence of length {expected_len}")
    if any(n not in df.columns for n in names_in):
        raise ValueError("'names_in' do not match column names in 'input'")
    rest = [c for c in df.columns if c not in names_in]
    return df[list(names_in) + rest]


def _summarise_numeric(df, id_col):
    """Per-ID aggregation matching R's summarise_all(min/max/mean/sum/count/
    sd/median): one <col>_<stat> column per numeric input column. R's sd()
    is the sample standard deviation (n-1); pandas .std() matches by
    default (numpy's does not).
    """
    numeric_cols = [c for c in df.columns if c != id_col and pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        return df[[id_col]].drop_duplicates().reset_index(drop=True)
    grouped = df.groupby(id_col, sort=False)[numeric_cols]
    parts = {
        "min": grouped.min(),
        "max": grouped.max(),
        "mean": grouped.mean(),
        "sum": grouped.sum(),
        "count": grouped.count(),
        "sd": grouped.std(),
        "median": grouped.median(),
    }
    out = parts["min"].copy()
    out.columns = [f"{c}_min" for c in numeric_cols]
    for stat in _STATS[1:]:
        block = parts[stat].copy()
        block.columns = [f"{c}_{stat}" for c in numeric_cols]
        out = out.join(block)
    return out.reset_index()


def _add_buffer(gdf, buf, separate_buffers=True):
    """CCAMLRGIS R: add_buffer.R. `buf` is in nautical miles."""
    buf_m = np.asarray(buf, dtype=float) * 1852
    buffered = gdf.copy()
    # resolution=30 matches sf::st_buffer's default nQuadSegs=30 (segments
    # per quarter-circle); shapely/geopandas default to 16, which produces
    # visibly different arc geometry at every convex vertex of a positive
    # buffer.
    buffered["geometry"] = gdf.geometry.buffer(buf_m, resolution=30)
    if not separate_buffers:
        union = buffered.geometry.union_all()
        buffered = gpd.GeoDataFrame({"ID": [1]}, geometry=[union], crs=gdf.crs)
    if "AreaKm2" in buffered.columns:
        buffered = buffered.rename(columns={"AreaKm2": "Unbuffered_AreaKm2"})
    buffered["Buffered_AreaKm2"] = (buffered.geometry.area / 1_000_000).round(1)
    return buffered


def _build_polys(input_df, densify=False, dlon=0.1, dlat=0.1):
    """CCAMLRGIS R: cPolys.R. `input_df` columns (after reordering): ID, Lat, Lon, ..."""
    id_col, lat_col, lon_col = input_df.columns[:3]
    ids = input_df[id_col].astype(str).unique()

    polygons = []
    for poly_id in ids:
        ring = input_df.loc[input_df[id_col].astype(str) == poly_id]
        lons = ring[lon_col].to_numpy(dtype=float)
        lats = ring[lat_col].to_numpy(dtype=float)
        lons = np.append(lons, lons[0])
        lats = np.append(lats, lats[0])

        diflons = np.abs(np.diff(lons))
        nonzero = diflons[diflons != 0]
        max_diflon = nonzero.max() if len(nonzero) else 0.0

        if max_diflon > 0.1 and densify:
            dense = densify_data(lons, lats, dlon=dlon, dlat=dlat)
            lons, lats = dense[:, 0], dense[:, 1]

        polygons.append(Polygon(np.column_stack([lons, lats])))

    data = input_df.drop(columns=[lat_col, lon_col]).rename(columns={id_col: "ID"})
    data["ID"] = data["ID"].astype(str)
    summary = _summarise_numeric(data, "ID")
    summary = summary.set_index("ID").loc[ids].reset_index()

    out = gpd.GeoDataFrame(summary, geometry=polygons, crs=WGS84)
    out = out.to_crs(CCAMLR_CRS)
    out["AreaKm2"] = (out.geometry.area / 1_000_000).round(1)
    centroids = out.geometry.centroid
    out["Labx"] = centroids.x
    out["Laby"] = centroids.y
    return out


def _build_lines(input_df, densify=False, dlon=0.1, dlat=0.1):
    """CCAMLRGIS R: cLines.R."""
    from pyproj import Geod

    id_col, lat_col, lon_col = input_df.columns[:3]
    ids = input_df[id_col].astype(str).unique()
    # R's st_length() on geographic (WGS84) coordinates uses s2 (spherical
    # great-circle length) by default -- sf_use_s2() is TRUE unless a
    # caller disables it, and cLines.R never does. This is NOT the WGS84
    # ellipsoidal geodesic; using pyproj's default ellipsoid here produced
    # lengths ~0.3-0.6% too long against the G2 fixtures. S2's Earth radius
    # (S2Earth::RadiusKm, the IUGG mean radius) is 6371.01 km -- passing it
    # as both semi-axes gives a sphere, matching s2's great-circle length.
    geod = Geod(a=6_371_010.0, b=6_371_010.0)

    lines = []
    lengths_km = {}
    for line_id in ids:
        pts = input_df.loc[input_df[id_col].astype(str) == line_id]
        lons = pts[lon_col].to_numpy(dtype=float)
        lats = pts[lat_col].to_numpy(dtype=float)

        diflons = np.abs(np.diff(lons))
        nonzero = diflons[diflons != 0]
        max_diflon = nonzero.max() if len(nonzero) else 0.0

        if max_diflon > 0.1 and densify:
            dense = densify_data(lons, lats, dlon=dlon, dlat=dlat)
            lons, lats = dense[:, 0], dense[:, 1]

        line = LineString(np.column_stack([lons, lats]))
        lines.append(line)
        lengths_km[line_id] = abs(geod.geometry_length(line)) / 1000

    data = input_df.drop(columns=[lat_col, lon_col]).rename(columns={id_col: "ID"})
    data["ID"] = data["ID"].astype(str)
    summary = _summarise_numeric(data, "ID")
    summary = summary.set_index("ID").loc[ids].reset_index()
    summary["LengthKm"] = [round(lengths_km[i], 4) for i in summary["ID"]]
    summary["LengthNm"] = [round(lengths_km[i] / 1.852, 4) for i in summary["ID"]]

    out = gpd.GeoDataFrame(summary, geometry=lines, crs=WGS84)
    return out.to_crs(CCAMLR_CRS)


def _build_points(input_df):
    """CCAMLRGIS R: cPoints.R."""
    lat_col, lon_col = input_df.columns[:2]
    out = gpd.GeoDataFrame(
        input_df.copy(),
        geometry=gpd.points_from_xy(input_df[lon_col], input_df[lat_col]),
        crs=WGS84,
    )
    out = out.to_crs(CCAMLR_CRS)
    out["x"] = out.geometry.x
    out["y"] = out.geometry.y
    out["ID"] = np.arange(1, len(out) + 1)
    return out


def create_polys(input, names_in=None, buffer=0, densify=True, clip=False, separate_buffers=True, dlon=0.1, dlat=0.1, coast=None):
    """Create polygons from a table of (ID, Lat, Lon) vertices. CCAMLRGIS R: create_Polys."""
    df = _reorder_columns(input.copy(), names_in, 3)
    output = _build_polys(df, densify=densify, dlon=dlon, dlat=dlat)
    buffer_arr = np.atleast_1d(buffer)
    if len(buffer_arr) == 1:
        if buffer_arr[0] > 0:
            output = _add_buffer(output, buffer, separate_buffers)
    else:
        output = _add_buffer(output, buffer, separate_buffers)
    if clip:
        output = clip_to_coast(output, coast)
    return output


def create_lines(input, names_in=None, buffer=0, densify=False, clip=False, separate_buffers=True, dlon=0.1, dlat=0.1, coast=None):
    """Create lines from a table of (ID, Lat, Lon) vertices. CCAMLRGIS R: create_Lines."""
    df = _reorder_columns(input.copy(), names_in, 3)
    output = _build_lines(df, densify=densify, dlon=dlon, dlat=dlat)
    buffer_arr = np.atleast_1d(buffer)
    if len(buffer_arr) == 1:
        if buffer_arr[0] > 0:
            output = _add_buffer(output, buffer, separate_buffers)
    else:
        output = _add_buffer(output, buffer, separate_buffers)
    if clip:
        output = clip_to_coast(output, coast)
    return output


def create_points(input, names_in=None, buffer=0, clip=False, separate_buffers=True, coast=None):
    """Create points from a table of (Lat, Lon, ...) locations. CCAMLRGIS R: create_Points."""
    df = _reorder_columns(input.copy(), names_in, 2)
    output = _build_points(df)
    buffer_arr = np.atleast_1d(buffer)
    if len(buffer_arr) == 1:
        if buffer_arr[0] > 0:
            output = _add_buffer(output, buffer, separate_buffers)
    else:
        output = _add_buffer(output, buffer, separate_buffers)
    if clip:
        output = clip_to_coast(output, coast)
    return output


def _seq_inclusive(a, b, step):
    """R's seq(a, b, by=step): a, a+step, ... up to but never exceeding b
    (exactly at b only if (b-a) is a multiple of step). Unlike a naive
    np.arange(a, b+step/2, step), this never overshoots b -- an overshoot
    here means an extra polygon vertex past the intended cell edge, which
    silently corrupted cells near the antimeridian (a longitude > 180)
    before this fix.
    """
    n = int(np.floor((b - a) / step + 1e-9)) + 1
    return a + np.arange(n) * step


def _degree_grid_polygon(glon, glat, dlon, dlat):
    xmin, xmax = glon - dlon / 2, glon + dlon / 2
    ymin, ymax = glat - dlat / 2, glat + dlat / 2
    if dlon <= 0.1:
        lons = [xmin, xmax, xmax, xmin]
        lats = [ymax, ymax, ymin, ymin]
    else:
        top = np.unique(np.concatenate([[xmin], _seq_inclusive(xmin, xmax, 0.1), [xmax]]))
        lons = list(top) + list(top[::-1])
        lats = [ymax] * len(top) + [ymin] * len(top)
    lons = lons + [lons[0]]
    lats = lats + [lats[0]]
    return Polygon(np.column_stack([lons, lats]))


def _match_points_to_cells(lats, lons, group):
    """Assign each (lat, lon) to the first intersecting cell in `group`
    (row order). CCAMLRGIS R: cGrid.r's point-matching loop.

    Deviation: R nudges unmatched (on-a-boundary) points by a small
    *randomly* signed offset and retries. This port nudges deterministically
    (always +epsilon, growing each retry) instead -- a boundary point only
    needs *some* small nudge to land unambiguously in a neighbouring cell,
    so which direction is arbitrary; a fixed direction is reproducible where
    R's is not (porting_notes.md deviation 10).
    """
    lats = np.asarray(lats, dtype=float).copy()
    lons = np.asarray(lons, dtype=float).copy()
    n = len(lats)
    result = np.full(n, np.nan)
    unresolved = np.arange(n)
    sindex = group.sindex
    deg_dev = 0.0

    while len(unresolved):
        x, y = _FORWARD.transform(lons[unresolved], lats[unresolved])
        for j, idx in enumerate(unresolved):
            cand = sindex.query(Point(x[j], y[j]), predicate="intersects")
            if len(cand):
                result[idx] = cand.min()
        still = unresolved[np.isnan(result[unresolved])]
        if len(still) == 0:
            break
        nudge = 0.0001 + deg_dev
        lats[still] += nudge
        lons[still] += nudge
        deg_dev += 0.0001
        unresolved = still

    return result


def create_polygrids(input, names_in=None, dlon=None, dlat=None, area=None, cuts=100, cols=("green", "yellow", "red"), blank=False):
    """Create a polygon grid to spatially aggregate data, in cells of a
    fixed lon/lat size (``dlon``/``dlat``) or of equal area (``area``, km2).
    ``blank=True`` produces an empty grid spanning ``input`` as
    ``[lat_min, lat_max, lon_min, lon_max]``, for reuse with
    ``assign_areas``. CCAMLRGIS R: cGrid.r.
    """
    if blank:
        lat_min_in, lat_max_in, lon_min_in, lon_max_in = input
        lat_min = lat_min_in
        lat_max = lat_max_in
        lon_min = lon_min_in
        lon_max = lon_max_in
        data = None
    else:
        df = _reorder_columns(pd.DataFrame(input).copy(), names_in, 2)
        cols_all = list(df.columns)
        data = df.rename(columns={cols_all[0]: "lat", cols_all[1]: "lon"})
        if data.shape[1] == 2:
            data["Count"] = 1
        lat_min = max(-89, np.floor(data["lat"].min()) - 1)
        lat_max = min(0, np.ceil(data["lat"].max()) + 1)
        lon_min = max(-180, np.floor(data["lon"].min() - 1))
        lon_max = min(180, np.ceil(data["lon"].max()) + 1)

    if area is None:
        # degree-cell mode
        if blank:
            glon, glat = np.meshgrid(
                _seq_inclusive(lon_min, lon_max, dlon), _seq_inclusive(lat_min, lat_max, dlat)
            )
            glon, glat = glon.ravel(), glat.ravel()
        else:
            snapped_lon = np.ceil((data["lon"] + dlon) / dlon) * dlon - dlon - dlon / 2
            snapped_lat = np.ceil((data["lat"] + dlat) / dlat) * dlat - dlat - dlat / 2
            uniq = pd.DataFrame({"Glon": snapped_lon, "Glat": snapped_lat}).drop_duplicates()
            glon, glat = uniq["Glon"].to_numpy(), uniq["Glat"].to_numpy()

        polygons = [_degree_grid_polygon(lo, la, dlon, dlat) for lo, la in zip(glon, glat)]
        group = gpd.GeoDataFrame(geometry=polygons, crs=WGS84).to_crs(CCAMLR_CRS)
        group["ID"] = np.arange(1, len(group) + 1)
        group["AreaKm2"] = (group.geometry.area / 1_000_000).round(1)
        group = group[["ID", "AreaKm2", "geometry"]]
    else:
        # equal-area mode
        area_m2 = area * 1e6
        s = np.sqrt(area_m2)
        polygons = []
        lat_n = lat_max
        lat_s = 0.0
        while lat_s > lat_min:
            lons_line = np.linspace(lon_min, lon_max, 10000)
            x, y = _FORWARD.transform(lons_line, np.full(10000, lat_n))
            strip_length = LineString(np.column_stack([x, y])).length
            n_pts = int(np.floor(strip_length / s))
            if n_pts <= 1:
                raise ValueError("Desired cell area is too large to fit in that space.")
            lx = strip_length / n_pts
            ly = area_m2 / lx
            lons_pts = np.linspace(lon_min, lon_max, n_pts)

            pt = create_points(pd.DataFrame({"Lat": [lat_n], "Lon": [lons_pts[0]]}))
            buffered = _add_buffer(pt, buf=ly / 1852)
            buffered_wgs84 = buffered.to_crs(WGS84)
            lat_s = buffered_wgs84.total_bounds[1]  # ymin

            def _strip_polygon_area(lat_n=lat_n, lat_s=lat_s, lon_a=lons_pts[0], lon_b=lons_pts[1]):
                lons = np.unique(np.concatenate([[lon_a], _seq_inclusive(lon_a, lon_b, 0.1), [lon_b]]))
                p_lon = np.concatenate([lons, lons[::-1], [lons[0]]])
                p_lat = np.concatenate([np.full(len(lons), lat_n), np.full(len(lons), lat_s), [lat_n]])
                pro = project_data(
                    pd.DataFrame({"Lat": p_lat, "Lon": p_lon}), names_in=["Lat", "Lon"], names_out=["y", "x"], append=False
                )
                return Polygon(np.column_stack([pro["x"], pro["y"]]))

            poly = _strip_polygon_area()
            poly_area = poly.area
            res_steps = [10 * 10.0**-i for i in range(16)]
            k = 0
            while area_m2 > poly_area and k < len(res_steps):
                lat_s_base = lat_s
                lat_s = lat_s - res_steps[k]
                if lat_s < -90:
                    lat_s = -90
                    break
                poly = _strip_polygon_area(lat_s=lat_s)
                poly_area = poly.area
                if area_m2 < poly_area:
                    lat_s = lat_s_base
                    poly = _strip_polygon_area(lat_s=lat_s)
                    poly_area = poly.area
                    k += 1

            for i in range(n_pts - 1):
                lon_a, lon_b = lons_pts[i], lons_pts[i + 1]
                lons = np.unique(np.concatenate([[lon_a], _seq_inclusive(lon_a, lon_b, 0.1), [lon_b]]))
                p_lon = np.concatenate([lons, lons[::-1], [lons[0]]])
                p_lat = np.concatenate([np.full(len(lons), lat_n), np.full(len(lons), lat_s), [lat_n]])
                pro = project_data(
                    pd.DataFrame({"Lat": p_lat, "Lon": p_lon}), names_in=["Lat", "Lon"], names_out=["y", "x"], append=False
                )
                polygons.append(Polygon(np.column_stack([pro["x"], pro["y"]])))

            lat_n = lat_s

        group = gpd.GeoDataFrame(geometry=polygons, crs=CCAMLR_CRS)
        group["ID"] = np.arange(1, len(group) + 1)
        group["AreaKm2"] = (group.geometry.area / 1_000_000).round(1)
        group = group[["ID", "AreaKm2", "geometry"]]

    centroids = group.geometry.centroid
    group["Centrex"] = centroids.x
    group["Centrey"] = centroids.y
    cen_ll = project_data(
        group[["Centrey", "Centrex"]], names_in=["Centrey", "Centrex"], names_out=["Centrelat", "Centrelon"], append=False, inverse=True
    )
    group["Centrelon"] = cen_ll["Centrelon"]
    group["Centrelat"] = cen_ll["Centrelat"]

    if blank:
        return group[["ID", "AreaKm2", "Centrex", "Centrey", "Centrelon", "Centrelat", "geometry"]]

    # _match_points_to_cells returns *positions* (0-based, into `group` as
    # it stands right now) via the spatial index, not group["ID"] values --
    # map through group["ID"] rather than assuming position == ID-1. That
    # assumption held only by the coincidence of ID being a contiguous
    # 1..N range with no rows dropped yet, and silently misaligned the
    # merge by one the moment it wasn't (it always wasn't, since ID is
    # 1-based and positions are 0-based) -- this previously dropped exactly
    # one populated cell from every non-blank grid.
    cell_pos = _match_points_to_cells(data["lat"].to_numpy(), data["lon"].to_numpy(), group)
    group_ids = group["ID"].to_numpy()
    data = data.copy()
    data["ID"] = group_ids[cell_pos.astype(int)].astype(str)
    group["ID"] = group["ID"].astype(str)
    group = group[group["ID"].isin(data["ID"].unique())].reset_index(drop=True)

    summary = _summarise_numeric(data.drop(columns=["lat", "lon"]), "ID")
    group = group.merge(summary, on="ID", how="left")

    exclude = {"Centrex", "Centrey", "Centrelon", "Centrelat"}
    numeric_cols = [
        c for c in group.columns if c not in exclude and c != "ID" and pd.api.types.is_numeric_dtype(group[c])
    ]
    for col in numeric_cols:
        if group[col].isna().all():
            group[f"Col_{col}"] = None
        else:
            result = add_colour(group[col].to_numpy(), cuts=cuts, cols=cols)
            group[f"Col_{col}"] = result["varcol"]

    if area is not None and group["AreaKm2"].nunique() != 1:
        import warnings

        warnings.warn("Equal-area gridding compromised. Check geometry.area on the output.")

    return group
