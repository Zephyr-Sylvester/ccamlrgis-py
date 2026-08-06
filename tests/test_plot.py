"""Smoke tests for ccamlrgis.plot. Plotting output is explicitly cosmetic
per the design doc's own faithfulness bar ("need not be pixel-identical"),
so these check that each helper runs, returns the expected artist type(s),
and doesn't silently no-op -- not pixel-level regression against R's
rendering. A pytest-mpl baseline-image harness (comparing against R's own
rendered output) would be a good, larger follow-up; not attempted here
(see PROGRESS.md).
"""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import pytest

import ccamlrgis.plot as ccplot
from ccamlrgis import create_pies, create_polys


@pytest.fixture
def ax():
    fig, ax = ccplot.basemap(figsize=(4, 4))
    yield ax
    plt.close(fig)


def test_basemap_returns_configured_axes():
    fig, ax = ccplot.basemap()
    assert fig is not None
    assert ax.get_aspect() in (1.0, "equal")
    plt.close(fig)


def test_basemap_attribution_renders_sources_and_projection():
    fig, ax = ccplot.basemap(
        attribution=["CCAMLR. (2026). Geographical data layer: ASDs. Version 2026, URL: https://example.com"]
    )
    assert len(ax.texts) == 1
    text = ax.texts[0].get_text()
    assert "CCAMLR." in text
    assert "Projection: EPSG:6932" in text
    plt.close(fig)


def test_basemap_no_attribution_by_default():
    fig, ax = ccplot.basemap()
    assert len(ax.texts) == 0
    plt.close(fig)


def test_add_colour_scale(ax):
    cax = ccplot.add_colour_scale(ax, cuts=[-1000, -500, -200, 0], cols=["#000080", "#0000ff", "#87ceeb"])
    assert len(cax.patches) == 3


def test_add_legend(ax):
    items = [
        ccplot.LegendItem(text="A", shape="rectangle", fill="red"),
        ccplot.LegendItem(text="B", shape="circle", fill="blue"),
        ccplot.LegendItem(text="C", shape="line", fill="green"),
        ccplot.LegendItem(text="D", shape="arrow", fill="orange"),
        ccplot.LegendItem(text="E", shape="none"),
    ]
    leg = ccplot.add_legend(ax, items=items, title="Title", subtitle="(sub)")
    assert len(leg.get_texts()) == 5


def test_add_pie_legend(ax, fixtures):
    pie_data = pd.read_csv(fixtures / "example_data" / "PieData.csv")
    pies = create_pies(pie_data, names_in=["Lat", "Lon", "Sp", "N"], size=50)

    pax = ccplot.add_pie_legend(ax, pies=pies, title="Species")
    assert len(pax.patches) > 0


def test_add_reference_grid(ax, fixtures):
    poly_data = pd.read_csv(fixtures / "example_data" / "PolyData.csv")
    polys = create_polys(poly_data)
    bounds = tuple(polys.total_bounds)

    artists = ccplot.add_reference_grid(ax, bounds=bounds, res_lat=5, res_lon=10)
    assert len(artists) > 0


def test_add_labels_table_mode(ax):
    table = pd.DataFrame({"x": [0, 1e6], "y": [0, 1e6], "text": ["here", "there"]})
    artists = ccplot.add_labels(ax, mode="table", label_table=table)
    assert len(artists) == 2
    assert artists[0].get_text() == "here"


def test_add_labels_auto_mode(ax, fixtures):
    labels_data = pd.read_csv(fixtures / "example_data" / "Labels.csv")
    artists = ccplot.add_labels(ax, mode="auto", layer="ASDs", labels_data=labels_data)
    assert len(artists) > 0


def test_add_labels_manual_mode_not_supported(ax):
    with pytest.raises(ValueError):
        ccplot.add_labels(ax, mode="manual")


def test_trim_circle_is_centred_on_pole():
    poly = ccplot.trim_circle(trim=-45)
    cx, cy = poly.centroid.x, poly.centroid.y
    assert abs(cx) < 1 and abs(cy) < 1
    assert poly.area > 0


def test_trim_circle_shrinks_closer_to_pole():
    far = ccplot.trim_circle(trim=-45)
    near = ccplot.trim_circle(trim=-75)
    assert near.area < far.area


def test_round_basemap_returns_configured_axes():
    fig, ax = ccplot.round_basemap(trim=-45)
    assert ax.get_aspect() in (1.0, "equal")
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    assert xmin == pytest.approx(-xmax)
    assert ymin == pytest.approx(-ymax)
    assert ax.get_xticks().size == 0
    plt.close(fig)


def test_round_basemap_margin_exceeds_trim_radius():
    fig, ax = ccplot.round_basemap(trim=-45, border_width=2.0)
    _, xmax = ax.get_xlim()
    r_trim = ccplot.trim_circle(trim=-45).bounds[2]
    assert xmax > r_trim
    plt.close(fig)


def test_add_border_ring_alternates_colours(ax):
    wedges = ccplot.add_border_ring(ax, trim=-45, n_segments=8)
    assert len(wedges) == 8
    facecolors = [w.get_facecolor() for w in wedges]
    assert facecolors[0] != facecolors[1]
    assert facecolors[0] == facecolors[2]


@pytest.mark.network
def test_add_labels_auto_mode_default_data(ax, monkeypatch, tmp_path):
    """labels_data=None should default to the cache-backed bundled Labels dataset."""
    import shutil
    from pathlib import Path

    artifacts = Path(__file__).parent.parent / "data_artifacts"
    if not artifacts.exists():
        pytest.skip("data_artifacts/ not built -- run tools/build_datasets.py first")
    for f in artifacts.iterdir():
        if f.name != "manifest.json":
            shutil.copy(f, tmp_path / f.name)
    monkeypatch.setenv("CCAMLRGIS_CACHE_DIR", str(tmp_path))

    artists = ccplot.add_labels(ax, mode="auto", layer="ASDs")
    assert len(artists) > 0
