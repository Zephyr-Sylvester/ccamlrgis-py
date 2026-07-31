"""CCAMLRGIS R: add_Cscale.R. Deviation from R: `pos='row/col'` (a base-
graphics grid-position idiom) is replaced by a matplotlib `loc=` edge
position ('right'/'left'/'top'/'bottom'), placed via
`mpl_toolkits.axes_grid1.make_axes_locatable` -- this carves out real
layout space next to `ax` (shrinking it to make room), rather than
floating an inset on top of it. Matches what R's `add_Cscale` achieves by
reserving margin space via `par(mar=...)` before plotting -- see
porting_notes.md.
"""

from collections.abc import Sequence

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.patches import Rectangle
from mpl_toolkits.axes_grid1 import make_axes_locatable

_VALID_LOC = ("right", "left", "top", "bottom")


def add_colour_scale(
    ax: Axes | None = None,
    cuts: Sequence[float] | None = None,
    cols: Sequence[str] | None = None,
    title: str = "Depth (m)",
    loc: str = "right",
    size: str = "5%",
    pad: float = 0.15,
    fontsize: float = 10,
    title_fontsize: float | None = None,
) -> Axes:
    """Add a discrete colour-class scale bar beside `ax`, resizing `ax` to
    make room for it rather than drawing on top of it. `cuts`/`cols` are
    typically produced by `add_colour()`. `loc` is one of "right", "left",
    "top", "bottom". `size` is the scale bar's thickness as a fraction of
    `ax`'s size (e.g. "5%"); `pad` is the gap between `ax` and the scale
    bar, in inches. Returns the new Axes created.
    """
    if cuts is None or cols is None:
        raise ValueError("'cuts' and 'cols' must be specified")
    if loc not in _VALID_LOC:
        raise ValueError(f"'loc' must be one of {_VALID_LOC}, got {loc!r}")
    ax = ax or plt.gca()
    cuts_arr = np.asarray(cuts, dtype=float)
    cols_list = list(cols)
    title_fontsize = title_fontsize or fontsize * 1.15
    n = len(cols_list)

    divider = make_axes_locatable(ax)
    cax: Axes = divider.append_axes(loc, size=size, pad=pad)

    vertical = loc in ("right", "left")
    for i, col in enumerate(cols_list):
        xy = (0, i) if vertical else (i, 0)
        cax.add_patch(Rectangle(xy, 1, 1, facecolor=col, edgecolor="black", linewidth=0.5))

    if vertical:
        cax.set_xlim(0, 1)
        cax.set_ylim(0, n)
        cax.set_xticks([])
        cax.set_yticks(np.arange(n + 1))
        cax.set_yticklabels([f"{c:g}" for c in cuts_arr], fontsize=fontsize)
        cax.yaxis.tick_right() if loc == "right" else cax.yaxis.tick_left()
    else:
        cax.set_ylim(0, 1)
        cax.set_xlim(0, n)
        cax.set_yticks([])
        cax.set_xticks(np.arange(n + 1))
        cax.set_xticklabels([f"{c:g}" for c in cuts_arr], fontsize=fontsize)
        cax.xaxis.tick_bottom() if loc == "bottom" else cax.xaxis.tick_top()

    cax.set_title(title, fontsize=title_fontsize, loc="left" if vertical else "center")
    return cax
