"""CCAMLRGIS R: add_labels.R. Deviation: only 'auto' and 'table' modes are
supported. R's 'manual' mode is interactive (click on a plot to place a
label, using terra::click/utils::edit) and has no meaningful headless
Python equivalent -- dropped per the design doc (section 1.2) and logged
as porting_notes.md deviation 2. Manual placement is done by editing a
label table and passing it via mode='table'.
"""

import matplotlib.pyplot as plt


def add_labels(ax=None, mode="auto", layer=None, labels_data=None, label_table=None, fontsize=10, fonttype=1, angle=0, colour="black"):
    """Add text labels to a plot.

    mode='auto': label the centres of polygon parts of layers loaded via
    the `load_*` functions. Requires `labels_data` (e.g.
    `ccamlrgis.datasets.load_example('Labels')`) and `layer` (one or more
    of "ASDs","SSRUs","RBs","SSMUs","MAs","MPAs","EEZs").

    mode='table': place labels from a table with columns
    x, y, text, and optionally fontsize, angle, col -- R's replacement for
    manual (click-to-place) label editing.
    """
    ax = ax or plt.gca()
    artists = []

    def _style(ft):
        weight = "bold" if ft in (2, 4) else "normal"
        style = "italic" if ft in (3, 4) else "normal"
        return weight, style

    if mode == "auto":
        if labels_data is None:
            raise ValueError("mode='auto' requires labels_data, e.g. ccamlrgis.datasets.load_example('Labels')")
        layers = [layer] if isinstance(layer, str) else list(layer)
        weight, style = _style(fonttype)
        rows = labels_data[labels_data["p"].isin(layers)]
        for _, row in rows.iterrows():
            artists.append(
                ax.text(row["x"], row["y"], row["t"], fontsize=fontsize, rotation=angle, color=colour, weight=weight, style=style, ha="center", va="center")
            )
    elif mode == "table":
        if label_table is None:
            raise ValueError("mode='table' requires label_table")
        for _, row in label_table.iterrows():
            weight, style = _style(row["fonttype"] if "fonttype" in row else fonttype)
            artists.append(
                ax.text(
                    row["x"], row["y"], row["text"],
                    fontsize=row["fontsize"] if "fontsize" in row else fontsize,
                    rotation=row["angle"] if "angle" in row else angle,
                    color=row["col"] if "col" in row else colour,
                    weight=weight, style=style, ha="center", va="center",
                )
            )
    else:
        raise ValueError("mode must be 'auto' or 'table' (R's interactive 'manual' mode is not supported)")

    return artists
