"""CCAMLRGIS R: add_Legend.R, add_PieLegend (Pies.R). Deviation: R's
add_Legend is ~680 lines of manual box/position arithmetic across 9 named
positions and 6 shape types with ~30 tunable options. Per the design doc's
own guidance ("port the output, not option-by-option"), this is a from-
scratch matplotlib implementation using its native legend machinery with
custom handles -- same visual result (a positioned box of labelled
shapes), far less surface area. See porting_notes.md.
"""

from dataclasses import dataclass

import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

_SHAPES = ("rectangle", "circle", "ellipse", "line", "arrow", "none")


@dataclass
class LegendItem:
    text: str
    shape: str = "rectangle"
    fill: str = "white"
    border: str = "black"
    linewidth: float = 1.0
    hatch: str | None = None


def _handle_for(item):
    if item.shape not in _SHAPES:
        raise ValueError(f"'shape' must be one of {_SHAPES}, got {item.shape!r}")
    if item.shape == "rectangle":
        return mpatches.Rectangle(
            (0, 0), 1, 1, facecolor=item.fill, edgecolor=item.border, linewidth=item.linewidth, hatch=item.hatch
        )
    if item.shape == "circle":
        return mpatches.Circle(
            (0.5, 0.5), 0.5, facecolor=item.fill, edgecolor=item.border, linewidth=item.linewidth, hatch=item.hatch
        )
    if item.shape == "ellipse":
        return mpatches.Ellipse(
            (0.5, 0.5), 1, 0.6, facecolor=item.fill, edgecolor=item.border, linewidth=item.linewidth, hatch=item.hatch
        )
    if item.shape == "line":
        return mlines.Line2D([], [], color=item.fill, linewidth=item.linewidth * 2)
    if item.shape == "arrow":
        return mpatches.FancyArrow(
            0,
            0.5,
            1,
            0,
            width=0.15,
            head_width=0.4,
            head_length=0.3,
            facecolor=item.fill,
            edgecolor=item.border,
            linewidth=item.linewidth,
        )
    return mpatches.Rectangle((0, 0), 1, 1, alpha=0)  # "none": blank space for the text only


def add_legend(ax=None, items=None, title=None, subtitle=None, loc="lower right", fontsize=10, title_fontsize=None):
    """Add a legend of custom shapes to `ax`. `items` is a list of
    `LegendItem`. Returns the `Legend` artist.
    """
    ax = ax or plt.gca()
    handles = [_handle_for(item) for item in items]
    labels = [item.text for item in items]

    legend_title = title
    if subtitle:
        legend_title = f"{title}\n{subtitle}" if title else subtitle

    return ax.legend(
        handles,
        labels,
        loc=loc,
        title=legend_title,
        fontsize=fontsize,
        title_fontsize=title_fontsize or fontsize * 1.15,
        frameon=True,
    )


def add_pie_legend(ax=None, pies=None, loc="lower left", width="30%", height="30%", title="Pie chart", fontsize=10):
    """Add a small pie-chart legend showing the classes/colours used by
    `create_pies()`'s output. CCAMLRGIS R: add_PieLegend (Pies.R).
    Deviation: uses matplotlib's native `Axes.pie()` rather than manually
    building slice geometry, since this is purely cosmetic.
    """
    ax = ax or plt.gca()
    pdata = pies.drop(columns="geometry") if hasattr(pies, "drop") else pies
    classes = pdata.loc[pdata["LegT"] == "Classes", "Leg"].iloc[0].split(";")
    cols = pdata.loc[pdata["LegT"] == "cols", "Leg"].iloc[0].split(";")

    pax = inset_axes(ax, width=width, height=height, loc=loc)
    pax.pie([1] * len(classes), colors=cols, labels=classes, textprops={"fontsize": fontsize})
    pax.set_title(title, fontsize=fontsize * 1.15)
    return pax
