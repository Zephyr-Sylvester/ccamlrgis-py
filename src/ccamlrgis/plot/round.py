"""New in this port -- not part of R CCAMLRGIS. Recreates the round-map /
checkerboard-border aesthetic of the SOmap R package
(https://github.com/AustralianAntarcticDivision/SOmap) using EPSG:6932's
own geometry directly, rather than SOmap's tiled-graticule-polygon
approach: since EPSG:6932 is a true polar-azimuthal projection centred
exactly on the pole, latitude circles are circles centred at the origin,
and the angle around that origin *is* longitude (confirmed empirically:
`lon=0 -> theta=90deg`, `lon=90 -> theta=0deg`, i.e. `theta = 90 - lon`).
So the round clip is just a circle and the checkerboard border is just a
ring of `matplotlib.patches.Wedge` patches -- no graticule-tiling library
needed. See docs/porting_notes.md.
"""

from collections.abc import Sequence
from typing import cast

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Wedge
from pyproj import Transformer
from shapely.geometry import Point, Polygon

from ..crs import CCAMLR_CRS, WGS84

_FORWARD = Transformer.from_crs(WGS84, CCAMLR_CRS, always_xy=True)


def _radius_at_lat(lat: float) -> float:
    x, y = _FORWARD.transform(0.0, lat)
    return float(np.hypot(x, y))


def trim_circle(trim: float = -45, quad_segs: int = 128) -> Polygon:
    """The circular boundary at latitude `trim`, in the CCAMLR CRS
    (EPSG:6932) -- centred on the projected pole, since EPSG:6932 is a
    true polar-azimuthal projection. Clip other layers to this before
    plotting them on a `round_basemap`, e.g.
    `coast_land.clip(trim_circle(-45)).plot(ax=ax, ...)` or
    `bathy.rio.clip([trim_circle(-45)])`. `quad_segs` is the number of
    line segments per quarter circle (higher = smoother).
    """
    return cast(Polygon, Point(0, 0).buffer(_radius_at_lat(trim), quad_segs=quad_segs))


def round_basemap(
    ax: Axes | None = None,
    figsize: tuple[float, float] = (9, 9),
    trim: float = -45,
    border_width: float = 2.0,
    margin: float = 1.02,
    attribution: str | Sequence[str] | None = None,
) -> tuple[Figure, Axes]:
    """Return a configured `(fig, ax)` for a round Southern Ocean map
    clipped at latitude `trim` -- the round-map counterpart to
    `basemap()`. Add layers clipped to `trim_circle(trim)` yourself (e.g.
    `coast_land.clip(trim_circle(trim)).plot(ax=ax, ...)`,
    `bathy.rio.clip([trim_circle(trim)])`), then finish with
    `add_border_ring(ax, trim=trim, width=border_width)` if wanted.

    `border_width` (degrees of latitude) only reserves axes margin for
    the checkerboard border ring here -- pass the same value to
    `add_border_ring` so the ring isn't clipped at the edge of the plot.
    `margin` is an extra multiplicative fudge factor (fraction of the
    outer radius) so the ring's own edge isn't flush with the figure
    border.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = cast(Figure, ax.figure)
    r_outer = _radius_at_lat(trim + border_width)
    lim = r_outer * margin
    ax.set_aspect("equal")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    for spine in ax.spines.values():
        spine.set_visible(False)

    if attribution is not None:
        sources = [attribution] if isinstance(attribution, str) else list(attribution)
        caption = "\n".join([*sources, f"Projection: {CCAMLR_CRS}"])
        ax.text(
            0.01,
            0.01,
            caption,
            transform=ax.transAxes,
            fontsize=6,
            color="black",
            ha="left",
            va="bottom",
            linespacing=1.4,
        )

    return fig, ax


def add_border_ring(
    ax: Axes | None = None,
    trim: float = -45,
    width: float = 2.0,
    n_segments: int = 24,
    colours: tuple[str, str] = ("black", "white"),
    edge_colour: str = "black",
    edge_linewidth: float = 0.5,
) -> list[Wedge]:
    """Add a checkerboard degree-ring border just outside the `trim`
    latitude circle, alternating `colours` around `n_segments` equal
    wedges -- the SOmap-style round-map border. Add this last, after
    every data layer (it's drawn on top, `zorder=5`).
    """
    ax = ax or plt.gca()
    r_inner = _radius_at_lat(trim)
    r_outer = _radius_at_lat(trim + width)
    step = 360 / n_segments
    wedges: list[Wedge] = []
    for i in range(n_segments):
        theta1 = i * step
        wedge = Wedge(
            (0, 0),
            r_outer,
            theta1,
            theta1 + step,
            width=r_outer - r_inner,
            facecolor=colours[i % 2],
            edgecolor=edge_colour,
            linewidth=edge_linewidth,
            zorder=5,
        )
        ax.add_patch(wedge)
        wedges.append(wedge)
    return wedges
