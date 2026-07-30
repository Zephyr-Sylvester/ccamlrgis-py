"""CCAMLRGIS R: add_RefGrid.R."""

import matplotlib.pyplot as plt
import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString
from shapely.geometry import box as shapely_box

from ..crs import CCAMLR_CRS, WGS84

_FORWARD = Transformer.from_crs(WGS84, CCAMLR_CRS, always_xy=True)


def _iter_lines(geom):
    if geom.is_empty:
        return
    if geom.geom_type == "LineString":
        yield geom
    elif geom.geom_type in ("MultiLineString", "GeometryCollection"):
        for g in geom.geoms:
            if g.geom_type == "LineString":
                yield g


def _first_point(geom):
    if geom.is_empty:
        return None
    if geom.geom_type == "Point":
        return geom
    if geom.geom_type in ("MultiPoint", "GeometryCollection"):
        pts = [g for g in geom.geoms if g.geom_type == "Point"]
        return pts[0] if pts else None
    return None


def add_reference_grid(ax=None, bounds=None, res_lat=1, res_lon=2, lab_lon=None, lat_range=(-80, -45), linewidth=1, line_colour="black", fontsize=10, font_colour="black", offset=None):
    """Add a Latitude/Longitude graticule to a map already in the CCAMLR
    CRS. CCAMLRGIS R: add_RefGrid.R.

    `bounds` is (xmin, ymin, xmax, ymax) in the target CRS; defaults to
    `ax`'s current data limits. Labels go along the left edge
    (latitudes) and bottom edge (longitudes) -- a simplified version of
    R's "whichever edge yields more labels" choice, since this is purely
    cosmetic (see porting_notes.md).
    """
    ax = ax or plt.gca()
    if bounds is None:
        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
    else:
        xmin, ymin, xmax, ymax = bounds
    bbox_poly = shapely_box(xmin, ymin, xmax, ymax)
    left_edge = LineString([(xmin, ymin), (xmin, ymax)])
    bottom_edge = LineString([(xmin, ymin), (xmax, ymin)])
    off = offset if offset is not None else 0.02 * (xmax - xmin)

    lats = np.arange(lat_range[0], lat_range[1] + res_lat / 2, res_lat)
    if lab_lon is not None:
        lons = np.unique(np.concatenate([np.arange(-180, 180 + res_lon / 2, res_lon), [lab_lon]]))
    else:
        lons = np.arange(-180, 180 + res_lon / 2, res_lon)

    artists = []

    for lat in lats:
        lon_line = np.linspace(-180, 180, 720)
        x, y = _FORWARD.transform(lon_line, np.full(720, lat))
        line = LineString(np.column_stack([x, y]))
        for seg in _iter_lines(line.intersection(bbox_poly)):
            artists.append(ax.plot(*seg.xy, linestyle=":", linewidth=linewidth, color=line_colour)[0])
        p = _first_point(line.intersection(left_edge))
        if p is not None:
            label = f"{abs(int(round(lat)))}S"
            artists.append(ax.text(p.x - off, p.y, label, fontsize=fontsize, color=font_colour, ha="right", va="center"))

    for lon in lons:
        lat_line = np.linspace(lat_range[0], lat_range[1], 360)
        x, y = _FORWARD.transform(np.full(360, lon), lat_line)
        line = LineString(np.column_stack([x, y]))
        for seg in _iter_lines(line.intersection(bbox_poly)):
            artists.append(ax.plot(*seg.xy, linestyle=":", linewidth=linewidth, color=line_colour)[0])
        p = _first_point(line.intersection(bottom_edge))
        if p is not None:
            if lon in (0, -180, 180):
                label = "180" if abs(lon) == 180 else "0"
            elif lon < 0:
                label = f"{abs(int(round(lon)))}W"
            else:
                label = f"{int(round(lon))}E"
            artists.append(ax.text(p.x, p.y - off, label, fontsize=fontsize, color=font_colour, ha="center", va="top"))

    return artists
