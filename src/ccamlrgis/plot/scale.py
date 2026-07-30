"""CCAMLRGIS R: add_Cscale.R. Deviation from R: `pos='row/col'` (a base-
graphics grid-position idiom) is replaced by matplotlib `loc=` strings via
`inset_axes` -- see porting_notes.md.
"""

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.axes_grid1.inset_locator import inset_axes


def add_colour_scale(ax=None, cuts=None, cols=None, title="Depth (m)", loc="center right", width="8%", height="60%", fontsize=10, title_fontsize=None):
    """Add a discrete colour-class scale bar to `ax`. `cuts`/`cols` are
    typically produced by `add_colour()`. Returns the inset Axes created.
    """
    ax = ax or plt.gca()
    cuts = np.asarray(cuts, dtype=float)
    cols = list(cols)
    title_fontsize = title_fontsize or fontsize * 1.15

    cax = inset_axes(ax, width=width, height=height, loc=loc, borderpad=2)
    n = len(cols)
    for i, col in enumerate(cols):
        cax.add_patch(plt.Rectangle((0, i), 1, 1, facecolor=col, edgecolor="black", linewidth=0.5))
    cax.set_xlim(0, 1)
    cax.set_ylim(0, n)
    cax.set_xticks([])
    cax.set_yticks(np.arange(n + 1))
    cax.set_yticklabels([f"{c:g}" for c in cuts], fontsize=fontsize)
    cax.yaxis.tick_right()
    cax.set_title(title, fontsize=title_fontsize, loc="left")
    return cax
