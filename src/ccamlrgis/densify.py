import warnings

import numpy as np
import numpy.typing as npt
from shapely.geometry import LineString, Point


def densify_data(
    lon: npt.ArrayLike, lat: npt.ArrayLike, dlon: float = 0.1, dlat: float = 0.1
) -> npt.NDArray[np.float64]:
    """Insert extra vertices along a polyline so no segment spans more than
    ``dlon``/``dlat`` degrees, and split any antimeridian-crossing segment
    into two. CCAMLRGIS R: DensifyData.R.

    R disables spherical geometry (``sf_use_s2(FALSE)``) for this function
    since it operates on straight lines in raw lon/lat degree space, not
    geodesics. shapely is always planar, so no equivalent toggle is needed.

    Returns an (n, 2) array of [lon, lat] columns.
    """
    lon = np.asarray(lon, dtype=float).copy()
    lat = np.asarray(lat, dtype=float).copy()

    lon[lon == 180] = 179.99999999
    lon[lon == -180] = -179.99999999

    # Step 1/2: fix antimeridian crossings
    lon_clean = []
    lat_clean = []
    for i in range(len(lon) - 1):
        lon1, lat1 = lon[i], lat[i]
        lon2, lat2 = lon[i + 1], lat[i + 1]
        alpha = abs(((lon2 - lon1 + 180) % 360) - 180)
        if alpha == 180:
            warnings.warn(
                "A line is exactly 180 degrees wide in longitude\nPlease add an intermediate point in the line\n"
            )
        crosses = (abs(lon1) >= 90 or abs(lon2) >= 90) and (np.sign(lon1) != np.sign(lon2)) and alpha < 180
        if crosses:
            if lon1 < lon2:  # ccw
                seg = LineString([(lon1 + 360, lat1), (lon2, lat2)])
            else:  # cw
                seg = LineString([(lon1, lat1), (lon2 + 360, lat2)])
            antimeridian = LineString([(180, -90), (180, 90)])
            crossing = seg.intersection(antimeridian)
            lat_am = crossing.y
            if lon1 < lon2:
                lon_clean += [lon1, -180, 180]
            else:
                lon_clean += [lon1, 180, -180]
            lat_clean += [lat1, lat_am, lat_am]
        else:
            lon_clean.append(lon1)
            lat_clean.append(lat1)
    lon_clean.append(lon[-1])
    lat_clean.append(lat[-1])

    # Step 2/2: densify each segment against a dlon x dlat graticule
    vs_lon = []
    vs_lat = []
    for i in range(len(lon_clean) - 1):
        lon1, lat1 = lon_clean[i], lat_clean[i]
        lon2, lat2 = lon_clean[i + 1], lat_clean[i + 1]

        if lon2 == lon1 and lon1 != 180:  # iso-longitude, no densifying needed
            vs_lon.append(lon1)
            vs_lat.append(lat1)
            continue
        if abs(lon1) == 180 and abs(lon2) == 180:  # antimeridian segment itself
            vs_lon.append(lon1)
            vs_lat.append(lat1)
            continue

        seg = LineString([(lon1, lat1), (lon2, lat2)])
        lon_min, lon_max = np.floor(min(lon1, lon2)) - 2 * dlon, np.ceil(max(lon1, lon2)) + 2 * dlon
        lat_min, lat_max = np.floor(min(lat1, lat2)) - 2 * dlat, np.ceil(max(lat1, lat2)) + 2 * dlat
        lats_grid = np.arange(lat_min, lat_max + dlat / 2, dlat)
        lons_grid = np.arange(lon_min, lon_max + dlon / 2, dlon)

        grid_lines = [LineString([(lon_min, la), (lon_max, la)]) for la in lats_grid]
        grid_lines += [LineString([(lo, lat_min), (lo, lat_max)]) for lo in lons_grid]

        # Round before deduping: a grid-line intersection that coincides with
        # a manually-added endpoint is very rarely bit-identical to it, so a
        # plain float set doesn't dedupe them (R's unique() on sf-computed
        # doubles apparently does; matching precision, not bit-pattern, is
        # what's needed here). 9 decimal degrees is sub-millimeter, far below
        # the 5-decimal precision the geospatial rules require of vertices.
        def _round(p: tuple[float, float]) -> tuple[float, float]:
            return (round(p[0], 9), round(p[1], 9))

        pts = {_round((lon1, lat1)), _round((lon2, lat2))}
        for gl in grid_lines:
            inter = seg.intersection(gl)
            if inter.is_empty:
                continue
            if inter.geom_type == "Point":
                pts.add(_round((inter.x, inter.y)))
            elif inter.geom_type == "MultiPoint":
                pts.update(_round((p.x, p.y)) for p in inter.geoms)

        ordered = sorted(pts, key=lambda p: seg.project(Point(p)))
        if ordered and ordered[-1] == _round((lon2, lat2)):
            ordered = ordered[:-1]

        vs_lon.extend(p[0] for p in ordered)
        vs_lat.extend(p[1] for p in ordered)

    vs_lon.append(lon_clean[-1])
    vs_lat.append(lat_clean[-1])

    return np.column_stack([vs_lon, vs_lat])
