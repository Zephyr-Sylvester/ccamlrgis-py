import numpy as np

# CCAMLRGIS R: data/Depth_cols.RData, Depth_cols2.RData, Depth_cuts.RData,
# Depth_cuts2.RData -- values confirmed via `rdata` against the R package's
# bundled data. *2 variants highlight the fishable depth range (-600 to
# -1800 m) with a distinct colour band. Use with add_colour(var, cuts=DEPTH_CUTS, cols=DEPTH_COLS).
DEPTH_COLS = [
    "#0000FF",
    "#061CFF",
    "#0C39FF",
    "#1256FF",
    "#1873FF",
    "#1E90FF",
    "#5CACEE",
    "#71BDF3",
    "#87CEFA",
    "#B0E2FF",
    "#D0EDFF",
    "#F0F8FF",
    "#FFFFFF",
    "#F2F2F2",
    "#E5E5E5",
]
DEPTH_COLS2 = [
    "#0000FF",
    "#061CFF",
    "#0C39FF",
    "#1256FF",
    "#1873FF",
    "#1E90FF",
    "#66CDAA",
    "#72E6BF",
    "#7FFFD4",
    "#B0E2FF",
    "#D0EDFF",
    "#F0F8FF",
    "#FFFFFF",
    "#F2F2F2",
    "#E5E5E5",
]
DEPTH_CUTS = [-8200, -7000, -6000, -5000, -4000, -3000, -1800, -1400, -1000, -600, -400, -200, 0, 50, 250, 500]
DEPTH_CUTS2 = DEPTH_CUTS

# Small vendored name table (not matplotlib): ccamlrgis.plot is the only
# module allowed to import matplotlib (design doc section 1.2), so add_colour
# -- used for non-plotting purposes too, e.g. colouring a GeoDataFrame column
# -- resolves its own named colours. Covers every colour name actually used
# in the R package; anything else, pass a hex code.
_NAMED_COLOURS = {
    "black": "#000000",
    "white": "#ffffff",
    "red": "#ff0000",
    "green": "#00ff00",
    "blue": "#0000ff",
    "yellow": "#ffff00",
    "cyan": "#00ffff",
    "magenta": "#ff00ff",
    "grey": "#bebebe",
    "gray": "#bebebe",
    "orange": "#ffa500",
    "purple": "#a020f0",
    "pink": "#ffc0cb",
    "brown": "#a52a2a",
    "lightblue": "#add8e6",
    "darkblue": "#00008b",
    "lightgreen": "#90ee90",
    "darkgreen": "#006400",
    "darkred": "#8b0000",
    "lightgrey": "#d3d3d3",
    "lightgray": "#d3d3d3",
    "darkgrey": "#a9a9a9",
    "darkgray": "#a9a9a9",
}


def _to_rgb(colour):
    if isinstance(colour, str) and colour.startswith("#"):
        hexcode = colour.lstrip("#")
        if len(hexcode) == 3:
            hexcode = "".join(c * 2 for c in hexcode)
        return tuple(int(hexcode[i : i + 2], 16) for i in (0, 2, 4))
    return _to_rgb(_NAMED_COLOURS[colour.lower()])


def _ramp_palette(cols, n):
    """Linear RGB interpolation across `cols`, `n` output hex colours --
    equivalent to R's grDevices::colorRampPalette(cols)(n).
    """
    stops = [_to_rgb(c) for c in cols]
    positions = [0.0] if n <= 1 else [i / (n - 1) for i in range(n)]
    seg = len(stops) - 1
    out = []
    for p in positions:
        t = p * seg
        i = min(int(t), seg - 1) if seg > 0 else 0
        frac = t - i
        r = stops[i][0] + (stops[i + 1][0] - stops[i][0]) * frac if seg > 0 else stops[0][0]
        g = stops[i][1] + (stops[i + 1][1] - stops[i][1]) * frac if seg > 0 else stops[0][1]
        b = stops[i][2] + (stops[i + 1][2] - stops[i][2]) * frac if seg > 0 else stops[0][2]
        out.append(f"#{round(r):02x}{round(g):02x}{round(b):02x}")
    return out


def add_colour(var, cuts=100, cols=("green", "yellow", "red")):
    """Map a numeric variable to colours, either as a continuous gradient
    (``cuts`` a single int: that many equally-spaced classes) or discrete
    classes (``cuts`` a sequence of breakpoints). CCAMLRGIS R: add_col.R.

    Returns a dict with ``varcol`` (one colour per input value), ``cuts``,
    and ``cols`` (the same shape R returns, for use with a colour-scale
    legend).
    """
    var = np.asarray(var, dtype=float)

    if np.ndim(cuts) == 0:
        cuts_to = np.linspace(np.nanmin(var), np.nanmax(var), int(cuts))
    else:
        cuts_to = np.asarray(cuts, dtype=float)

    n_classes = len(cuts_to) - 1
    cols_to = _ramp_palette(cols, n_classes)

    if np.nanmin(var) == np.nanmax(var):
        varcol = np.full(var.shape, cols_to[0], dtype=object)
    else:
        # right=False, include_lowest=True to match R's cut(..., right=FALSE, include.lowest=TRUE)
        idx = np.digitize(var, cuts_to[1:-1], right=False)
        idx = np.clip(idx, 0, n_classes - 1)
        varcol = np.array([cols_to[i] for i in idx], dtype=object)
        varcol[np.isnan(var)] = None

    return {"cuts": cuts_to, "cols": np.array(cols_to, dtype=object), "varcol": varcol}
