"""Optional plotting layer. This is the ONLY ccamlrgis module that imports
matplotlib (design doc section 1.2) -- import ccamlrgis.plot explicitly
(``pip install ccamlrgis[plot]``); the rest of the library works without
matplotlib installed at all.
"""

import matplotlib.pyplot as plt

from ..crs import CCAMLR_CRS
from .grid import add_reference_grid
from .labels import add_labels
from .legend import LegendItem, add_legend, add_pie_legend
from .scale import add_colour_scale


def basemap(ax=None, figsize=(8, 8), xlim=None, ylim=None, attribution=None):
    """Return a configured `(fig, ax)` in the CCAMLR CRS (EPSG:6932). New
    in this port -- the R package draws onto base graphics' current device
    instead of returning a figure/axes handle. Add layers with
    geopandas'/xarray's own ``.plot(ax=ax, ...)``, or the ``add_*`` helpers
    in this module.

    `attribution`, if given, renders CCAMLR geospatial rule 9's "cite data
    sources and the projection used" caption in the bottom-left corner --
    pass a string, or a list of strings (e.g. loaded layers' own
    `.attrs["citation"]`, rule 8's citations).
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure
    ax.set_aspect("equal")
    if xlim is not None:
        ax.set_xlim(xlim)
    if ylim is not None:
        ax.set_ylim(ylim)
    ax.set_xticks([])
    ax.set_yticks([])

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


__all__ = [
    "LegendItem",
    "add_colour_scale",
    "add_labels",
    "add_legend",
    "add_pie_legend",
    "add_reference_grid",
    "basemap",
]
