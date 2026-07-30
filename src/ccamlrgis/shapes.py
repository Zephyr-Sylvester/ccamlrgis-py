from math import comb

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, MultiLineString, MultiPoint, Polygon, box
from shapely.ops import unary_union

from .analysis import project_data
from .colours import _to_rgb
from .crs import CCAMLR_CRS


def _get_perpendicular(x, y, d):
    """For each point in (x, y), the two points offset perpendicular to the
    local segment direction (to the previous point; to the next point for
    the first one) at distance d. Returns (2n,) arrays: point i's two
    offsets are at [2*i] and [2*i+1]. CCAMLRGIS R: GetPerp.R.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    ox = np.empty(2 * n)
    oy = np.empty(2 * n)

    def _offsets(xi, yi, xj, yj):
        # perpendicular to the segment (xj,yj)->(xi,yi), at point (xi,yi)
        with np.errstate(divide="ignore", invalid="ignore"):
            m = (yi - yj) / (xi - xj)
        if m == 0:
            m = 1e-12
        dx = np.sqrt(d**2 / (1 + (1 / m**2)))
        x1, x2 = xi + dx, xi - dx
        y1 = yi - (1 / m) * (x1 - xi)
        y2 = yi - (1 / m) * (x2 - xi)
        return x1, y1, x2, y2

    ox[0], oy[0], ox[1], oy[1] = _offsets(x[0], y[0], x[1], y[1])
    for i in range(1, n):
        ox[2 * i], oy[2 * i], ox[2 * i + 1], oy[2 * i + 1] = _offsets(x[i], y[i], x[i - 1], y[i - 1])
    return ox, oy


def _bezier_curve(control_points, n_points):
    """Bernstein-basis Bezier curve, matching R's bezier::bezier() default
    algorithm. `control_points` is (m, d); returns (n_points, d).
    """
    control_points = np.asarray(control_points, dtype=float)
    n = len(control_points) - 1
    t = np.linspace(0, 1, n_points)
    result = np.zeros((n_points, control_points.shape[1]))
    for i in range(n + 1):
        bernstein = comb(n, i) * t**i * (1 - t) ** (n - i)
        result += np.outer(bernstein, control_points[i])
    return result


def create_ellipse(latc, lonc, lmaj, lmin, ang=0, n_points=100, direction="cw", yx=False):
    """Create an ellipse polygon. CCAMLRGIS R: create_Ellipse.R."""
    if not yx:
        cen = project_data(pd.DataFrame({"Lat": [latc], "Lon": [lonc]}), names_in=["Lat", "Lon"])
    else:
        cen = pd.DataFrame({"Y": [latc], "X": [lonc]})
    cx, cy = cen["X"].iloc[0], cen["Y"].iloc[0]

    lmaj_m = lmaj * 1000
    lmin_m = lmin * 1000
    ang_rad = ang * np.pi / 180
    th = np.linspace(0, 2 * np.pi, n_points) if direction == "ccw" else np.linspace(2 * np.pi, 0, n_points)

    x = lmaj_m * np.cos(ang_rad) * np.cos(th) + lmin_m * np.sin(ang_rad) * np.sin(th) + cx
    y = lmin_m * np.cos(ang_rad) * np.sin(th) - lmaj_m * np.sin(ang_rad) * np.cos(th) + cy
    if x[0] != x[-1] or y[0] != y[-1]:
        x, y = np.append(x, x[0]), np.append(y, y[0])

    poly = Polygon(np.column_stack([x, y]))
    return gpd.GeoDataFrame(cen, geometry=[poly], crs=CCAMLR_CRS)


def create_hashes(pol, angle=45, spacing=1, width=1):
    """Hatching lines filling a polygon, as real geometry. CCAMLRGIS R:
    create_Hashes.R. `pol` is a single polygon (a GeoDataFrame/GeoSeries row
    or a shapely geometry).
    """
    if angle == 0:
        angle = 0.00000001
    if angle == 180:
        angle = 180.00000001
    if angle == -180:
        angle = -180.00000001
    if angle == 360:
        angle = 359.999999999

    if hasattr(pol, "geometry"):
        geom = pol.geometry.iloc[0] if hasattr(pol.geometry, "iloc") else pol.geometry
        crs = pol.crs
    else:
        geom, crs = pol, None

    xmin, ymin, xmax, ymax = geom.bounds
    bbox_poly = box(xmin, ymin, xmax, ymax)
    xc, yc = (xmin + xmax) / 2, (ymin + ymax) / 2
    d = max(xmax - xmin, ymax - ymin)
    ang_rad = angle * np.pi / 180
    x1, y1 = xc + d * np.cos(ang_rad), yc + d * np.sin(ang_rad)
    x2, y2 = xc + d * np.cos(ang_rad + np.pi), yc + d * np.sin(ang_rad + np.pi)

    lines = [LineString([(x1, y1), (x2, y2)])]

    ox, oy = _get_perpendicular(np.array([x1, x2]), np.array([y1, y2]), 50000 * spacing)
    a = np.array([[ox[0], oy[0]], [ox[2], oy[2]]])
    b = np.array([[ox[1], oy[1]], [ox[3], oy[3]]])
    lines.append(LineString(a))
    lines.append(LineString(b))

    while LineString(a).intersects(bbox_poly):
        ox, oy = _get_perpendicular(a[:, 0], a[:, 1], 50000 * spacing)
        a = np.array([[ox[0], oy[0]], [ox[2], oy[2]]])
        lines.append(LineString(a))
    while LineString(b).intersects(bbox_poly):
        ox, oy = _get_perpendicular(b[:, 0], b[:, 1], 50000 * spacing)
        b = np.array([[ox[1], oy[1]], [ox[3], oy[3]]])
        lines.append(LineString(b))

    buffered = MultiLineString(lines).buffer(10000 * width)
    clipped = buffered.intersection(geom)
    return gpd.GeoSeries([clipped], crs=crs)


def _rgba_ramp(colours, alphas, n):
    """Linear RGBA interpolation across `colours`/`alphas`, `n` output
    (r,g,b,a) tuples in [0,1]. CCAMLRGIS R: grDevices::colorRampPalette
    with alpha=TRUE, fed opacities of 1-Atrans.
    """
    stops = [(*(c / 255 for c in _to_rgb(col)), 1 - a) for col, a in zip(colours, alphas)]
    positions = [0.0] if n <= 1 else [i / (n - 1) for i in range(n)]
    seg = len(stops) - 1
    out = []
    for p in positions:
        t = p * seg
        i = min(int(t), seg - 1) if seg > 0 else 0
        frac = t - i if seg > 0 else 0.0
        out.append(
            tuple(stops[i][k] + (stops[i + 1][k] - stops[i][k]) * frac if seg > 0 else stops[0][k] for k in range(4))
        )
    return out


def create_arrow(
    input,
    n_points=50,
    pwidth=5,
    hlength=15,
    hwidth=10,
    dlength=0,
    arrow_type="normal",
    colour="green",
    transparency=0,
    yx=False,
):
    """Create a (possibly curved, possibly segmented/dashed) arrow.
    CCAMLRGIS R: create_Arrow.R. `input` has 2 or 3 columns: Lat, Lon (or Y,
    X if `yx=True`), and an optional integer weight (biases the Bezier
    curve toward that control point). Returns a GeoDataFrame with an RGBA
    `col` column (R spelling kept per design doc section 1.1) -- geometry
    only, never drawn (design doc section 1.2).
    """
    colours = [colour] if isinstance(colour, str) else list(colour)
    alphas = [transparency] if isinstance(transparency, (int, float)) else list(transparency)
    if arrow_type == "normal" and len(colours) > 1:
        raise ValueError("A 'normal' arrow can only have one colour.")
    if len(colours) > 1 and len(alphas) == 1:
        alphas = alphas * len(colours)
    if len(colours) != len(alphas):
        raise ValueError("len(transparency) should equal len(colour).")

    pwidth_m = pwidth * 10000
    hlength_m = hlength * 10000
    hwidth_m = max(hwidth * 10000, pwidth_m)

    df = pd.DataFrame(input).copy()
    if df.shape[1] == 2:
        df["w"] = 1
    df.iloc[:, 2] = df.iloc[:, 2].round().astype(int)
    if df.iloc[:, 2].isna().any():
        raise ValueError("Missing weight(s) in the input.")

    pts = pd.DataFrame({"Lat": df.iloc[:, 0], "Lon": df.iloc[:, 1], "w": df.iloc[:, 2]})
    if len(df) > 2 and pts["w"].nunique() > 1:
        pts = pts.loc[pts.index.repeat(pts["w"])].reset_index(drop=True)

    if not yx:
        proj = project_data(pts, names_in=["Lat", "Lon"], append=False)
        control = proj[["X", "Y"]].to_numpy()
    else:
        control = pts[["Lon", "Lat"]].to_numpy()  # yx=True: Lat col holds Y, Lon col holds X

    bs = _bezier_curve(control, n_points)  # columns: X, Y
    line = LineString(bs)

    head_frac = 1 - (hlength_m / line.length)
    pt1 = np.array(line.interpolate(head_frac, normalized=True).coords[0])

    ofs = abs(hlength_m * (1 - (pwidth_m / hwidth_m)))
    ofs -= 0.1 * ofs
    pt2_frac = 1 - ((hlength_m - ofs) / line.length)
    n_sub = max(int(n_points * pt2_frac) + 2, 2)
    sub_ts = np.linspace(0, pt2_frac, n_sub)
    pt2 = np.array([line.interpolate(t, normalized=True).coords[0] for t in sub_ts])

    tip = bs[-1]
    ox, oy = _get_perpendicular(np.array([pt1[0], tip[0]]), np.array([pt1[1], tip[1]]), hwidth_m)
    head_pts = MultiPoint([(ox[0], oy[0]), (ox[1], oy[1]), tuple(tip)])
    head = head_pts.convex_hull

    ox, oy = _get_perpendicular(pt2[:, 0], pt2[:, 1], pwidth_m)
    # R: Seqs = seq(1, nrow(Perps), by=2); Seqs = Seqs[-length(Seqs)] -- indices into the
    # (2*len(pt2),) flat perpendicular-offset array, stepping 2 at a time, dropping the last.
    flat_seqs = list(range(0, 2 * len(pt2), 2))[:-1] if len(pt2) > 0 else []
    if dlength > 0:
        dlength_i = max(round(dlength), 1)
        keep = np.tile(np.repeat([1, 0], dlength_i), len(flat_seqs) // (2 * dlength_i) + 1)[: len(flat_seqs)]
        flat_seqs = [s for s, k in zip(flat_seqs, keep) if k == 1]

    segments = []
    for i in flat_seqs:
        pts4 = MultiPoint([(ox[i], oy[i]), (ox[i + 1], oy[i + 1]), (ox[i + 2], oy[i + 2]), (ox[i + 3], oy[i + 3])])
        segments.append(pts4.convex_hull)

    # Fix head: some tail segments (built to slightly overlap the head, via
    # `ofs` above) can end up fully inside it -- truncate at the last one,
    # unconditionally, before branching on arrow_type (matches R exactly).
    contained = [i for i, seg in enumerate(segments) if shapely.contains_properly(head, seg)]
    if contained:
        segments = segments[: max(contained) + 1]

    if arrow_type == "normal":
        merged = unary_union([head, *segments]).buffer(1).buffer(-1)
        rgba = _rgba_ramp(colours, alphas, 1)
        out = gpd.GeoDataFrame({"col": [rgba[0]]}, geometry=[merged], crs=CCAMLR_CRS)
    elif arrow_type == "dashed":
        kept_segments = [seg for seg in segments if not shapely.contains_properly(head, seg)]
        geoms = [*kept_segments, head]
        cols = _rgba_ramp(colours, alphas, len(geoms))
        out = gpd.GeoDataFrame({"col": cols}, geometry=geoms, crs=CCAMLR_CRS)
    else:
        raise ValueError("arrow_type must be 'normal' or 'dashed'")

    return out


def create_circular_arrow(
    latc=-67,
    lonc=-30,
    lmaj=800,
    lmin=500,
    ang=140,
    n_points_ellipse=100,
    direction="cw",
    n_arrows=1,
    spacing=0,
    start=0,
    n_points_arrow=50,
    pwidth=5,
    hlength=15,
    hwidth=10,
    dlength=0,
    arrow_type="normal",
    colour="green",
    transparency=0,
    yx=False,
    input=None,
):
    """One or more arrows along an elliptical (or custom, via `input`) path.
    Defaults trace a simplified Weddell Sea gyre. CCAMLRGIS R:
    create_CircularArrow.R.
    """
    if input is None:
        el = create_ellipse(latc, lonc, lmaj, lmin, ang=ang, n_points=n_points_ellipse, direction=direction, yx=yx)
        el_geom = el.geometry.iloc[0]
    else:
        el_geom = input.geometry.iloc[0] if hasattr(input, "geometry") else input

    coords = np.array(el_geom.exterior.coords)
    elp = pd.DataFrame({"Y": coords[:, 1], "X": coords[:, 0]}).drop_duplicates().reset_index(drop=True)

    ip = round(len(elp) * start + 1)  # 1-based, per R
    ip = min(max(1, ip), len(elp))
    if ip != 1 and ip != len(elp):
        ip0 = ip - 1
        elp = pd.concat([elp.iloc[ip0:], elp.iloc[:ip0]]).reset_index(drop=True)
    elp = pd.concat([elp, elp.iloc[[0]]]).reset_index(drop=True)

    elp["a"] = 1
    if n_arrows > 1:
        elp["a"] = pd.cut(np.arange(1, len(elp) + 1), n_arrows, labels=False) + 1

    def _arrow(pts):
        return create_arrow(
            pts[["Y", "X"]],
            yx=True,
            n_points=n_points_arrow,
            pwidth=pwidth,
            hlength=hlength,
            hwidth=hwidth,
            dlength=dlength,
            arrow_type=arrow_type,
            colour=colour,
            transparency=transparency,
        )

    arr = None
    for i in range(1, n_arrows + 1):
        pts = elp[elp["a"] == i].reset_index(drop=True)
        if spacing >= 0:
            if i > 1:
                prev_last = elp[elp["a"] == i - 1].iloc[[-1]]
                pts = pd.concat([prev_last, pts]).reset_index(drop=True)
            trimmed = pts.iloc[: len(pts) - spacing]
            arri = _arrow(trimmed)
            arri["a"], arri["n"] = i, 1
        elif n_arrows == 1:
            wrapped = pd.concat([pts, pts.iloc[:-spacing]]).reset_index(drop=True)
            arri = _arrow(wrapped)
            arri["a"], arri["n"] = i, 1
        else:
            src_a = elp["a"].max() if i == 1 else i - 1
            idxs = elp.index[elp["a"] == src_a].tolist()
            adp = idxs[spacing:]  # tail(x, -Spc) with Spc<0 here == last -spacing elements
            combined = pd.concat([elp.loc[adp], pts]).reset_index(drop=True)
            arri = _arrow(combined)
            arri["a"] = i
            arri["n"] = np.arange(1, len(arri) + 1)

        arr = arri if arr is None else pd.concat([arr, arri], ignore_index=True)
        if arr["n"].max() > 3:
            thr = arr["n"].max() // 3
            arr = pd.concat([arr[arr["n"] <= thr], arr[arr["n"] > thr]]).reset_index(drop=True)

    return gpd.GeoDataFrame(arr, geometry="geometry", crs=CCAMLR_CRS)
