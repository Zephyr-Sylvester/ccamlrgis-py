"""CCAMLRGIS R: add_Cscale.R. Deviation from R: `pos='row/col'` (a base-
graphics grid-position idiom) is replaced by matplotlib `loc=` strings via
`inset_axes` -- see porting_notes.md.
"""

from collections.abc import Sequence

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.patches import Rectangle
from mpl_toolkits.axes_grid1.inset_locator import inset_axes


def add_colour_scale(
    ax: Axes | None = None,
    cuts: Sequence[float] | None = None,
    cols: Sequence[str] | None = None,
    title: str = "Depth (m)",
    loc: str = "center right",
    width: str = "8%",
    height: str = "60%",
    fontsize: float = 10,
    title_fontsize: float | None = None,
) -> Axes:
    """Add a discrete colour-class scale bar to `ax`. `cuts`/`cols` are
    typically produced by `add_colour()`. Returns the inset Axes created.
    """
    if cuts is None or cols is None:
        raise ValueError("'cuts' and 'cols' must be specified")
    ax = ax or plt.gca()
    cuts_arr = np.asarray(cuts, dtype=float)
    cols_list = list(cols)
    title_fontsize = title_fontsize or fontsize * 1.15

    cax: Axes = inset_axes(ax, width=width, height=height, loc=loc, borderpad=2)
    n = len(cols_list)
    for i, col in enumerate(cols_list):
        cax.add_patch(Rectangle((0, i), 1, 1, facecolor=col, edgecolor="black", linewidth=0.5))
    cax.set_xlim(0, 1)
    cax.set_ylim(0, n)
    cax.set_xticks([])
    cax.set_yticks(np.arange(n + 1))
    cax.set_yticklabels([f"{c:g}" for c in cuts_arr], fontsize=fontsize)
    cax.yaxis.tick_right()
    cax.set_title(title, fontsize=title_fontsize, loc="left")
    return cax
