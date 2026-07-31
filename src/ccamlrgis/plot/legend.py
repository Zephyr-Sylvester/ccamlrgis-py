"""CCAMLRGIS R: add_Legend.R, add_PieLegend (Pies.R). Deviation: R's
add_Legend is ~680 lines of manual box/position arithmetic across 9 named
positions and 6 shape types with ~30 tunable options. Per the design doc's
own guidance ("port the output, not option-by-option"), this is a from-
scratch matplotlib implementation using its native legend machinery with
custom handles -- same visual result (a positioned box of labelled
shapes), far less surface area. See porting_notes.md.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import geopandas as gpd
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.legend import Legend
from matplotlib.legend_handler import HandlerPatch
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

_SHAPES = ("rectangle", "circle", "ellipse", "line", "arrow", "none")


def _circle_icon(
    legend: Legend,
    orig_handle: mpatches.Patch,
    xdescent: float,
    ydescent: float,
    width: float,
    height: float,
    fontsize: float,
) -> mpatches.Circle:
    r = min(width, height) / 2
    return mpatches.Circle((width / 2 - xdescent, height / 2 - ydescent), r)


def _ellipse_icon(
    legend: Legend,
    orig_handle: mpatches.Patch,
    xdescent: float,
    ydescent: float,
    width: float,
    height: float,
    fontsize: float,
) -> mpatches.Ellipse:
    return mpatches.Ellipse((width / 2 - xdescent, height / 2 - ydescent), width, height * 0.6)


def _arrow_icon(
    legend: Legend,
    orig_handle: mpatches.Patch,
    xdescent: float,
    ydescent: float,
    width: float,
    height: float,
    fontsize: float,
) -> mpatches.FancyArrow:
    return mpatches.FancyArrow(
        -xdescent,
        height / 2 - ydescent,
        width,
        0,
        width=height * 0.2,
        head_width=height * 0.7,
        head_length=width * 0.3,
        length_includes_head=True,
    )


# matplotlib's default Patch legend handler (HandlerPatch, patch_func=None)
# always draws a plain Rectangle icon, copying only style properties
# (facecolor/edgecolor/linewidth/hatch) from the real handle -- not its
# shape. Rectangle and the alpha=0 "none" placeholder happen to look
# right anyway (a rectangle IS what they should show), but Circle/
# Ellipse/FancyArrow all rendered as boxes without this -- see
# porting_notes.md.
_HANDLER_MAP: dict[Any, HandlerPatch] = {
    mpatches.Circle: HandlerPatch(patch_func=_circle_icon),
    mpatches.Ellipse: HandlerPatch(patch_func=_ellipse_icon),
    mpatches.FancyArrow: HandlerPatch(patch_func=_arrow_icon),
}


@dataclass
class LegendItem:
    text: str
    shape: str = "rectangle"
    fill: str = "white"
    border: str = "black"
    linewidth: float = 1.0
    hatch: str | None = None


def _handle_for(item: LegendItem) -> mpatches.Patch | mlines.Line2D:
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


def add_legend(
    ax: Axes | None = None,
    items: Sequence[LegendItem] | None = None,
    title: str | None = None,
    subtitle: str | None = None,
    loc: str = "lower right",
    fontsize: float = 10,
    title_fontsize: float | None = None,
) -> Legend:
    """Add a legend of custom shapes to `ax`. `items` is a list of
    `LegendItem`. Returns the `Legend` artist.
    """
    if items is None:
        raise ValueError("'items' must be specified")
    ax = ax or plt.gca()
    handles = [_handle_for(item) for item in items]
    labels = [item.text for item in items]

    legend_title = title
    if subtitle:
        legend_title = f"{title}\n{subtitle}" if title else subtitle

    # matplotlib's stub narrows loc= to a Literal of its named positions;
    # ours stays a plain str since matplotlib itself also accepts numeric
    # location codes at runtime.
    return ax.legend(  # type: ignore[call-overload,no-any-return]
        handles,
        labels,
        handler_map=_HANDLER_MAP,
        loc=loc,
        title=legend_title,
        fontsize=fontsize,
        title_fontsize=title_fontsize or fontsize * 1.15,
        frameon=True,
    )


def add_pie_legend(
    ax: Axes | None = None,
    pies: gpd.GeoDataFrame | None = None,
    loc: str = "lower left",
    width: str = "30%",
    height: str = "30%",
    title: str = "Pie chart",
    fontsize: float = 10,
) -> Axes:
    """Add a small pie-chart legend showing the classes/colours used by
    `create_pies()`'s output. CCAMLRGIS R: add_PieLegend (Pies.R).
    Deviation: uses matplotlib's native `Axes.pie()` rather than manually
    building slice geometry, since this is purely cosmetic.
    """
    if pies is None:
        raise ValueError("'pies' must be specified")
    ax = ax or plt.gca()
    pdata = pies.drop(columns="geometry") if hasattr(pies, "drop") else pies
    classes = pdata.loc[pdata["LegT"] == "Classes", "Leg"].iloc[0].split(";")
    cols = pdata.loc[pdata["LegT"] == "cols", "Leg"].iloc[0].split(";")

    pax: Axes = inset_axes(ax, width=width, height=height, loc=loc)
    pax.pie([1] * len(classes), colors=cols, labels=classes, textprops={"fontsize": fontsize})
    pax.set_title(title, fontsize=fontsize * 1.15)
    return pax
