# Porting notes: intentional deviations from the R package

Every place where the Python port's behaviour differs from CCAMLRGIS (R) is
recorded here as it is discovered, with: R behaviour, Python behaviour,
reason, and the impact on users. Nothing in this list is accidental — where
the R package rounds, sorts, or uses a particular statistic, the port matches
it unless a deviation is logged below (§7.6 of the port design).

Status: Phase 1 in progress (`project_data`, `densify_data` implemented and
passing against G1 fixtures). Deviations 1-6 below were known up front from
the design decisions in §1-§2 of the port design and logged pre-emptively per
§7.4; deviation 7 was found while implementing `densify_data`.

## 1. Plotting: stateful base graphics → explicit Axes

**R behaviour:** `add_Cscale`, `add_Legend`, `add_RefGrid`, `add_labels`,
`add_PieLegend` draw onto R's current graphics device as a side effect, with
no return value users are expected to use.

**Python behaviour:** every plotting helper lives in `ccamlrgis.plot`, takes
`ax: matplotlib.axes.Axes` as its first argument (default `plt.gca()`), and
**returns** the artist(s) it added instead of relying on global device state.

**Reason:** global-device drawing is incompatible with Jupyter's inline
figure model, headless use, and composing multiple maps in one script.
Explicit-Axes is the standard matplotlib idiom.

**Impact on users:** R scripts that called `add_Cscale(...)` for its side
effect must be rewritten as `ccamlrgis.plot.add_colour_scale(ax, ...)` and,
if the return value is needed, captured explicitly. No behavioural change to
the rendered output beyond this calling convention.

## 2. `add_labels(mode='manual')` interactivity dropped

**R behaviour:** `mode='manual'` opens an interactive `terra::click()` /
`utils::edit()` session so a user can place labels by hand in the R graphics
window.

**Python behaviour:** only `mode='auto'` (automatic placement) and
`mode='table'` (labels supplied as a pre-built `label_table` DataFrame) are
implemented. There is no `mode='manual'`.

**Reason:** an interactive, blocking, device-coupled workflow has no
faithful equivalent across matplotlib backends (inline Jupyter, headless
scripts, non-interactive CI) and would reintroduce the global-device
coupling deviation 1 removes.

**Impact on users:** manual label placement is done by editing the label
table (adjusting `Labx`/`Laby`/text columns) and passing it via
`mode='table'`, rather than clicking on a plot. This is documented as the
replacement workflow, not silently unsupported.

## 3. `get_iso_polys`: `isoband` → matplotlib contours / rasterio polygonisation

**R behaviour:** uses the `isoband` package (`isobands()` / `iso_to_sfg()`)
to convert a classified raster into banded polygons.

**Python behaviour:** uses `matplotlib.contour` path extraction into
`shapely` polygons, or `rasterio.features.shapes` on a classified array
(final choice made during implementation, see the function's own notes).

**Reason:** `isoband` has no direct Python port; both matplotlib-contour and
rasterio-polygonize are established equivalents, but they can differ from
`isoband` and from each other at pixel boundaries.

**Impact on users:** band boundary geometry may differ from R at the
sub-pixel level. Gate G3 requires total area per band to match R to within
0.1% — this is the function most likely to hide a subtle divergence, and it
gets extra validation attention for that reason.

## 4. `add_Cscale(pos='1/1', ...)` grid-position string → matplotlib `loc=`

**R behaviour:** `pos` is a base-graphics grid-position idiom (e.g.
`'1/1'`) describing where in a notional grid over the plot the colour scale
is drawn.

**Python behaviour:** `ccamlrgis.plot.add_colour_scale` accepts a matplotlib-
style `loc=` string (e.g. `'lower right'`) and/or explicit `inset_axes`
placement, not the `'row/col'` string.

**Reason:** the R idiom is specific to base graphics' device model and has no
meaning in matplotlib's Axes/figure coordinate system.

**Impact on users:** existing `pos='1/1'`-style calls must be translated to a
`loc=` string by hand; `docs/r_to_python.md` documents the replacement
argument.

## 5. Bundled data → cache-backed downloads

**R behaviour:** `data/*.RData` (`PolyData`, `GridData`, `PointData`,
`LineData`, `PieData`, `PieData2`, `Labels`, `Coast`, the `Depth_*` palettes)
and `inst/extdata/SmallBathy.tif` ship inside the installed package; no
network access is required to use example data or `SmallBathy()`.

**Python behaviour:** nothing is bundled in the wheel. `small_bathy()` and
`ccamlrgis.datasets.load_example(...)` fetch from a versioned GitHub Release
asset set on first use and cache locally (§1.3); `load_*` WFS functions
always required network access in R too, but the port additionally requires
it for what R shipped as static data.

**Reason:** keeping the wheel under 1 MB and letting data be versioned
independently of code (so a code release can never silently change the data
under a user), at the cost of requiring a first-use network fetch (or
`prefetch()`) even for what R users could previously use fully offline.

**Impact on users:** first use of any example dataset or `small_bathy()`
requires network access (or a pre-warmed cache via
`ccamlrgis.cache.prefetch()`); offline failures raise
`CCAMLRGISOfflineError` naming the missing layer rather than failing
silently or returning stale data. The test suite works around this with
committed fixtures under `tests/fixtures/` so tests never require network
(§1.3).

## 6. R recycling / partial-matching semantics not reproduced

**R behaviour:** R vector recycling (e.g. a length-1 argument silently
recycled against a longer vector) and partial argument-name matching
(`Dens=` matching `Densify=` if unambiguous) are language features CCAMLRGIS
implicitly relies on in places.

**Python behaviour:** neither is reproduced. Arguments must be the correct
length (or explicitly broadcast, e.g. with `numpy`) and must be spelled out
in full (or matched positionally); no partial keyword matching.

**Reason:** these are R-language, not CCAMLRGIS-specific, behaviours with no
Python equivalent worth emulating — reproducing them would mean writing a
recycling/partial-matching shim for its own sake, which contradicts writing
idiomatic Python.

**Impact on users:** a length-mismatched argument that R would have silently
recycled will raise in Python (from numpy/pandas broadcasting rules or an
explicit length check) instead of silently succeeding. This is considered a
correctness improvement, not a regression, but is called out here because it
is a behavioural difference on the same input.

## 7. `densify_data`: R's occasional duplicate consecutive vertex not reproduced

**R behaviour:** on some antimeridian-crossing segments, `DensifyData()`
emits an exact-duplicate consecutive vertex (confirmed on both the
`antimeridian_ccw` and `antimeridian_cw` G1 fixtures: 206 output rows, only
202 distinct). This comes from R's own `st_intersection()`/`unique()`
pipeline: a grid line crossing the segment very close to another grid line's
crossing produces two points that aren't bit-identical doubles (so R's
`unique()` keeps both), but are identical at the precision the fixture CSV
is written at.

**Python behaviour:** `densify_data` rounds candidate vertices to 9 decimal
degrees (sub-millimeter, far below the 5-decimal precision the geospatial
rules require) before deduplicating, so this pair collapses to one vertex.

**Reason:** replicating R's exact duplicate here would mean matching GEOS's
specific floating-point computation path bit-for-bit, which isn't practical
and wouldn't be meaningful even if achieved — the "faithfulness" bar (§0) is
about matching geometry and values, not replaying R's internal float noise.
The rounding-before-dedup approach was also required to fix a real bug it
uncovered: without it, some segments produced *extra* un-deduplicated
vertices where a manually-added endpoint and a computed grid intersection
landed on the same coordinate but different floats (see `building_polygons_
P1`/`P3` and `exactly_180_wide` in the G1 test history) — same fix, and this
direction of it is a genuine correctness improvement, not just a cosmetic
difference from R.

**Impact on users:** on the small subset of segments where this R quirk
occurs, the Python port returns one fewer (geometrically redundant) vertex
than R. Polygon/line shape, area, and all downstream computations are
unaffected — the dropped vertex sat exactly on the retained one. The G1 test
suite (`tests/test_densify.py`) collapses R's consecutive exact-duplicate
rows before comparing, rather than requiring raw vertex-count equality.
