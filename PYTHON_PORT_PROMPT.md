# Claude Code prompt — Port CCAMLRGIS (R) to a Python library

> Paste the whole of this file as the opening prompt in a Claude Code session started at the
> root of this repository. It is written to be executed in phases; do not skip the validation
> gates.

---

## 0. Context and mission

You are porting the **CCAMLRGIS R package** (v4.3.1, CRAN, GPL-3, authored by the CCAMLR
Secretariat) to a Python library. Both source repositories are already on disk:

| Path | What it is |
|---|---|
| `./` (repo root) | Local copy of https://github.com/ccamlr/CCAMLRGIS — the R package. `R/` holds ~4,850 lines across 30 files, `man/` the Rd docs, `README.md` the 2,400-line worked tutorial, `data/` the `.RData` example datasets, `inst/extdata/SmallBathy.tif` the bundled raster. |
| `./geospatial_operations-main/` | Local copy of https://github.com/ccamlr/geospatial_operations — the Secretariat's geospatial rules, the Building Polygons workflow, the GeoPackage dataset build scripts, and numerical tools (Fishery Concentration Index/Areas, acoustic survey design). |

**Purpose of the original package**, which the port must preserve: *simplify the production of
maps in the CAMLR Convention Area*, via two categories of functions — **load functions** that
import spatial layers from the online [CCAMLR GIS](https://gis.ccamlr.org/) (ASD boundaries,
SSRUs, MPAs, EEZs, coastline, bathymetry), and **create functions** that build layers from user
data (polygons, lines, points, grids, stations, pies, arrows).

**Faithfulness bar.** For any function that produces geometry or numbers, the Python output must
match the R output to within floating-point tolerance on the same input. Cosmetic plotting output
need not be pixel-identical, but must be visually equivalent and carry the same information.

---

## 1. Non-negotiable design decisions

These have already been decided. Do not relitigate them; if you believe one is wrong, raise it
once, concisely, and then follow it unless told otherwise.

### 1.1 Naming: pure Pythonic `snake_case`
- `load_ASDs()` → `load_asds()`, `create_Polys()` → `create_polys()`, `add_Cscale()` →
  `add_colour_scale()`, `Clip2Coast()` → `clip_to_coast()`, `SmallBathy()` → `small_bathy()`.
- Arguments too: `NamesIn=` → `names_in=`, `Densify=` → `densify=`, `Dlon=`/`Dlat=` →
  `dlon=`/`dlat=`, `SeparateBuf=` → `separate_buffers=`, `Buffer=` → `buffer=`.
- **No R-named aliases.** Instead, ship `docs/r_to_python.md`: a complete two-column mapping table
  of every R function and argument to its Python equivalent, so existing CCAMLR R scripts can be
  translated by hand.
- Column names *inside returned data* keep the R spellings (`AreaKm2`, `Labx`, `Laby`,
  `Buffered_AreaKm2`, `Centrelon`, `Col_Catch_sum`, …) because downstream CCAMLR workflows,
  GeoPackages and published outputs depend on them. Document this asymmetry explicitly.

### 1.2 Plotting: explicit-Axes matplotlib, no global state
The R package draws with base graphics onto the current device; `add_Cscale`, `add_Legend`,
`add_RefGrid`, `add_labels` and `add_PieLegend` are stateful side-effecting calls. Do **not**
reproduce that model.

- Every plotting helper takes `ax: matplotlib.axes.Axes` as its first argument (defaulting to
  `plt.gca()` for interactive/Jupyter convenience) and **returns** the artist(s) it added.
- Geometry-producing functions (`create_pies`, `create_arrow`, `create_hashes`,
  `create_ellipse`, `create_circular_arrow`, `get_iso_polys`) return GeoDataFrames with a
  colour column — they never draw. Drawing is always a separate, optional call. This is the key
  separation that makes the library usable headless, in scripts, in Jupyter, and with
  non-matplotlib backends.
- Provide a thin optional convenience layer (`ccamlrgis.plot`) with `basemap(...)` returning a
  configured `(fig, ax)` in EPSG:6932, plus the `add_*` helpers. Users who prefer
  `gdf.plot(ax=ax)`, GeoPandas explore, folium or cartopy must be able to ignore it entirely —
  so `ccamlrgis.plot` must be the only module that imports matplotlib, and matplotlib must be an
  optional extra (`pip install ccamlrgis[plot]`).

### 1.3 Data: download-on-demand with a local cache, nothing bundled
- No `.RData`, no `SmallBathy.tif`, no GeoPackages inside the wheel. Target wheel size < 1 MB.
- Implement `ccamlrgis.cache` with a single resolution order:
  1. explicit `path=` argument, 2. `CCAMLRGIS_CACHE_DIR` env var, 3. platform cache dir via
  `platformdirs` (`~/.cache/ccamlrgis` on Linux/macOS).
- Every fetch: ETag/Last-Modified conditional request, atomic write to a temp file then rename,
  checksum recorded in a `manifest.json` next to the data, and a `force_refresh=False` argument.
- `ccamlrgis.cache.prefetch(layers=..., bathy_res=...)` warms the cache in one call so users can
  go offline afterwards; `ccamlrgis.cache.info()` lists what is cached, with sizes and fetch dates.
- Offline behaviour must fail loudly and helpfully: on network error, raise
  `CCAMLRGISOfflineError` naming the missing layer and telling the user to run `prefetch()` or
  point `CCAMLRGIS_CACHE_DIR` at an existing cache. Never silently return stale or empty data.
- `small_bathy()` and the example datasets (`PolyData`, `GridData`, `PointData`, `LineData`,
  `PieData`, `PieData2`, `Labels`, `Coast`) are all cache-backed downloads exposed as
  `ccamlrgis.datasets.load_example("PolyData")` etc. See §4 for how to produce them.
- **Consequence to handle deliberately:** the test suite must not depend on the network. Commit
  small fixtures under `tests/fixtures/` (a few hundred kB total, outside the package
  directory so they are not shipped) and make network tests opt-in via
  `pytest -m network`.

### 1.4 Build in phases with validation gates
Do not attempt all 41 functions in one pass. Each phase ends with a gate that must pass before
the next begins. Gates are defined in §6.

---

## 2. Geospatial rules that constrain the implementation

From `geospatial_operations-main/README.md`, endorsed by the Scientific Committee in 2023
(SC-CAMLR-42, para 2.30). Encode these in the library's behaviour and state them in the docs:

1. All GIS objects use **EPSG:6932** (WGS 84 / NSIDC EASE-Grid 2.0 South, South Pole Lambert
   azimuthal equal-area). This is the library's default output CRS everywhere.
2. **Lines of more than 0.1° of longitude must be densified.** This is the `DensifyData` /
   `densify` machinery — the single most important thing to port correctly.
3. Polygon vertices are given **clockwise, in decimal degrees, with at least five decimals**.
4. **Vertices must be added where polygons meet** (WG-FSA-2023 Fig. 1).
5. **Inland vertices** are used for polygons bound by any coastline.
6. Polygons are **clipped to all coastlines** using the most recent coastline data.
7. The coastline comes from the SCAR Antarctic Digital Database and, where needed, Natural Earth.
8. Analyses cite CCAMLR geospatial data as:
   `CCAMLR. (Year). Geographical data layer: (Layer name). Version (Version), URL: (URL)`.
9. **All maps cite data sources and the projection used.**

Two of these should become code, not just prose:

- Add `ccamlrgis.validate.check_geospatial_rules(gdf, ...)` returning a structured report
  (dataclass with a list of violations) covering: CRS is 6932; no un-densified segment exceeds
  `dlon`; ring orientation is clockwise in geographic coordinates; coordinate precision ≥ 5
  decimals where source coordinates are available; geometry validity.
- Add `ccamlrgis.cite.layer_citation(layer, year=None)` producing the Rule-8 string from the
  WFS layer metadata, and have `plot.basemap()` accept `attribution=` that renders the Rule-9
  source/projection caption. Make the citation string reachable from every loaded layer via a
  `.attrs["citation"]` entry on the returned GeoDataFrame.

---

## 3. Library shape and toolchain

Recommended layout — deviate only with a stated reason:

```
ccamlrgis-py/
├── pyproject.toml            # hatchling backend; requires-python = ">=3.10"; authoritative deps
├── environment.yml           # conda-forge dev/Jupyter env (see §8.4)
├── environment-r.yml         # separate R env, only for generating G0 golden outputs
├── README.md                 # port of the R README tutorial, as runnable Python
├── LICENSE                   # GPL-3 (the R package is GPL-3; the port is a derivative work)
├── NOTICE                    # attribution to CCAMLR Secretariat + original authors
├── src/ccamlrgis/
│   ├── __init__.py           # curated public API, __version__, __all__
│   ├── crs.py                # CCAMLR_CRS = 6932, WGS84 = 4326, helpers
│   ├── cache.py              # download/cache/manifest/prefetch/info
│   ├── datasets.py           # load_example(), small_bathy()
│   ├── load.py               # load_asds, load_ssrus, ... , load_bathy
│   ├── densify.py            # densify_data + antimeridian handling
│   ├── create.py             # create_polys/_lines/_points/_polygrids
│   ├── stations.py           # create_stations
│   ├── pies.py               # create_pies (+ pie legend geometry)
│   ├── shapes.py             # create_arrow, create_circular_arrow, create_ellipse, create_hashes
│   ├── analysis.py           # get_depths, seabed_area, assign_areas, get_c_intersection,
│   │                         #   get_iso_polys, rotate_obj, project_data, clip_to_coast
│   ├── colours.py            # add_col, depth_cols/cuts, depth_cols2/cuts2 palettes
│   ├── validate.py           # geospatial-rule checks
│   ├── cite.py               # Rule 8/9 citations
│   ├── plot/
│   │   ├── __init__.py       # basemap()
│   │   ├── scale.py          # add_colour_scale  (R: add_Cscale)
│   │   ├── legend.py         # add_legend, add_pie_legend
│   │   ├── grid.py           # add_reference_grid (R: add_RefGrid)
│   │   └── labels.py         # add_labels
│   └── py.typed
├── tests/
│   ├── fixtures/             # committed golden outputs from R (see §6)
│   └── test_*.py
├── tools/
│   ├── export_r_reference.R  # runs the R package, writes golden outputs to tests/fixtures
│   └── build_datasets.py     # converts data/*.RData + SmallBathy.tif into published artifacts
├── docs/
│   ├── r_to_python.md        # complete R→Python mapping table
│   ├── geospatial_rules.md
│   └── porting_notes.md      # every intentional deviation, with rationale
└── notebooks/
    ├── 01_basemaps.ipynb
    ├── 02_create_functions.ipynb
    ├── 03_load_functions.ipynb
    └── 04_building_polygons.ipynb   # the geospatial_operations workflow, in Python
```

**Dependency mapping** (core deps kept deliberately small):

| R | Python | Notes |
|---|---|---|
| `sf` | `geopandas` (≥1.0) + `shapely` (≥2.0) | GeoDataFrame is the universal return type |
| `terra` | `rasterio` + `rioxarray`/`xarray` | rasters returned as `xarray.DataArray` with rio accessor |
| `sf::st_read(WFS url)` | `requests` + `geopandas.read_file` on cached GeoJSON | do not stream directly; always cache first |
| `dplyr` | `pandas` groupby/agg | |
| `isoband` | `matplotlib.contour` → `shapely` polygonisation, or `rasterio.features.shapes` | see `get_iso_polys` notes below |
| `lwgeom::st_linesubstring` | `shapely.ops.substring` | direct equivalent |
| `lwgeom::st_transform_proj` | `pyproj.Transformer` | needed for the non-sf projection paths |
| `bezier::bezier` | small vendored Bézier evaluator (~20 lines) or `scipy` | avoid a dep for one function |
| `grDevices::chull` | `scipy.spatial.ConvexHull` or `shapely.convex_hull` | prefer shapely, drop scipy |
| base graphics | `matplotlib` (optional extra) | |

Toolchain: `uv` for env/lockfile, `ruff` for lint+format, `mypy --strict` on `src/`, `pytest` +
`pytest-cov`, `nbval` or `jupytext` to execute the notebooks in CI, GitHub Actions matrix on
3.10–3.13 × {ubuntu, macos, windows}.

**Jupyter is the primary consumption environment.** That means: every public function has a
useful `__repr__`-friendly return (GeoDataFrame or DataArray, never an opaque object); no
function prints to stdout unless `verbose=True`; long operations (`create_stations`,
`create_polygrids` with `area=`) accept `progress=False` and use `tqdm` when `True` (optional
extra); docstrings are NumPy-style with a runnable Examples section.

---

## 4. Producing the downloadable data artifacts

Because nothing is bundled, you must first *create* the artifacts the cache will fetch.
`tools/build_datasets.py` should:

1. Read `data/*.RData` with the pure-Python [`rdata`](https://pypi.org/project/rdata/) package
   (no R installation required). Fall back to `Rscript` + `sf::st_write` only if `rdata` cannot
   handle an object.
2. Write tabular examples (`PolyData`, `GridData`, `PointData`, `LineData`, `PieData`,
   `PieData2`, `Labels`) as **CSV** — they are small, human-readable, and diffable.
3. Write `Coast` as **GeoPackage** (it is an sf object, ~470 kB compressed).
4. Copy `inst/extdata/SmallBathy.tif` as-is (Cloud-Optimised GeoTIFF if you can reproject-free
   convert it; otherwise leave it).
5. Emit `manifest.json` with SHA-256 for every artifact.
6. Publish these as a **GitHub Release asset set** on the new Python repo, versioned
   independently of the code (`data-v1`). The cache module pins the data version, so a code
   release can never silently change the data underneath a user.

Bathymetry stays a direct passthrough to CCAMLR:
`https://gis.ccamlr.org/geoserver/www/GEBCO2024_{res}.tif` for `res ∈ {500, 1000, 2500, 5000}` —
these are large (the 500 m grid is multi-GB), so `load_bathy()` must stream with a progress bar,
support resume, and verify size before use.

WFS endpoints to port verbatim (note: the R package uses **http**, not https — test whether
https now works and prefer it, but keep http as a documented fallback):

```
http://gis.ccamlr.org/geoserver/gis/ows?service=WFS&version=1.0.0&request=GetFeature&outputFormat=json&typeName=gis:<LAYER>
```

| Python function | `<LAYER>` |
|---|---|
| `load_asds()`      | `statistical_areas_6932` |
| `load_ssrus()`     | `ssrus_6932` |
| `load_coastline()` | `coastline_v1_6932` |
| `load_rbs()`       | `research_blocks_6932` |
| `load_ssmus()`     | `ssmus_6932` |
| `load_mas()`       | `omas_6932` |
| `load_mpas()`      | `mpas_6932` |
| `load_eezs()`      | `eez_6932` |

All are re-projected to 6932 after read (the R code does this even though the layers are already
6932 — keep the step, it normalises the CRS object).

---

## 5. Function inventory and per-function porting notes

41 functions. Exported ones are marked ★; the rest are internal helpers that should become
private (`_name`) or be folded into their callers.

### Phase 1 — Foundations
| R | Python | Notes |
|---|---|---|
| `CCAMLRp` | `ccamlrgis.crs.CCAMLR_CRS` | the proj4/EPSG constant |
| ★`project_data` | `project_data` | pandas in/out; `inv=` → `inverse=`; preserve the NA-fill/restore behaviour and the "not on Earth" warnings verbatim (they become `warnings.warn`) |
| `DensifyData` | `densify_data` | **The critical one.** Two steps: (a) fix antimeridian crossings by inserting paired ±180 vertices at the interpolated crossing latitude, preserving cw/ccw direction; (b) for each segment, intersect with a `dlon`×`dlat` graticule and insert the intersection points in along-line order. R disables s2 for this (`sf_use_s2(FALSE)`) — shapely 2 is already planar, so no equivalent is needed, but say so in a comment. Watch the ±180 → ±179.99999999 nudge and the "line exactly 180° wide" warning. |
| `cPolys` / `cLines` / `cPoints` | `_build_polys` / `_build_lines` / `_build_points` | private constructors; note `cPolys` closes the ring by appending the first index, aggregates numeric columns with min/max/mean/sum/count/sd/median, then projects and computes `AreaKm2`, `Labx`, `Laby`. R's `sd` is the **sample** sd (n−1) — pandas `.std()` matches by default; numpy's does not. |
| `add_buffer` | `_add_buffer` | buffer distance is in **nautical miles** (`buf * 1852`); renames `AreaKm2` → `Unbuffered_AreaKm2` and adds `Buffered_AreaKm2` |
| ★`Clip2Coast` | `clip_to_coast` | `st_difference` against the simplified `Coast` layer; adds `Clipped_AreaKm2` / `Buffered_and_clipped_AreaKm2`. Under the download-everything model this triggers a cache fetch — document that, and add `coast=` so a user can pass their own (e.g. the high-res `load_coastline()`, which the R docs recommend for accuracy). |
| ★`load_ASDs` … `load_EEZs` (8) | `load_asds` … `load_eezs` | thin wrappers over the cache + WFS |
| ★`load_Bathy` | `load_bathy` | `LocalFile=FALSE` → `path=None`; returns `xarray.DataArray` |
| ★`SmallBathy` | `small_bathy` | cache-backed |
| — | `Depth_cols`, `Depth_cuts`, `Depth_cols2`, `Depth_cuts2` | palettes as module constants in `colours.py`; `*2` variants highlight the fishable depth range |

### Phase 2 — Create functions
| R | Python | Notes |
|---|---|---|
| ★`create_Polys` | `create_polys` | `densify=True` by default here (unlike lines/points); densify only fires when max non-zero |Δlon| > 0.1 |
| ★`create_Lines` | `create_lines` | `densify=False` default |
| ★`create_Points` | `create_points` | no densify |
| ★`create_PolyGrids` | `create_polygrids` | two modes: degree cells (`dlon`/`dlat`) and **equal-area** cells (`area=` in km²), plus `blank=True` for an empty grid. The equal-area algorithm is the fiddliest part — port `cGrid.r` line by line and validate cell areas to ±0.1 km². Generates `Col_<var>_<stat>` colour columns via `add_col`. |
| ★`add_col` | `add_colour` (alias-free; document the R name) | returns a dict-like with `varcol`, `cuts`, `cols`; underpins grid colouring |
| ★`assign_areas` | `assign_areas` | point-in-polygon assignment with optional buffer; `AreaNameFormat='GAR_Long_Label'` → `area_name_format=`. Must handle points falling in multiple overlapping layers and preserve the R column-appending order. |

### Phase 3 — Analysis
| R | Python | Notes |
|---|---|---|
| ★`get_depths` | `get_depths` | raster sampling at points; use `rasterio.sample` |
| ★`seabed_area` | `seabed_area` | area by depth class, default `depth_classes=(-600, -1800)` (the fishable range). Compute on the equal-area projection so cell area is exact; cross-check against `terra::expanse`. |
| ★`get_C_intersection` | `get_c_intersection` | intersection of two great-circle-ish segments defined by lat/lon; `Plot=TRUE` → return-only plus a separate plot helper |
| ★`get_iso_polys` | `get_iso_polys` | R uses `isoband`. Python: `matplotlib.contour` → paths → shapely polygons, or `rasterio.features.shapes` on a classified array. **Validate carefully** — this is where a subtle difference will hide. Compare total area per band against R to <0.1%. |
| ★`Rotate_obj` | `rotate_obj` | rotates an object about a chosen central longitude; implemented as a CRS re-definition (`+lon_0=`), not a geometric affine — keep it that way |
| `GetPerp` | `_get_perpendicular` | helper for arrow widths |
| ★`create_Stations` | `create_stations` | random/stratified station generation inside a polygon within a depth range; `Nauto` (automatic N per stratum) and `dist` (minimum spacing) modes. **Stochastic** — the port must accept `rng=` / `seed=` and cannot be validated by equality; validate distributionally (see §6). |

### Phase 4 — Shapes and pies (geometry only)
| R | Python | Notes |
|---|---|---|
| ★`create_Pies` | `create_pies` | returns pie-slice polygons as a GeoDataFrame with colour column; supports `SizeVar`, `GridKm` aggregation, and an `Other` threshold that merges small classes |
| ★`create_Arrow` | `create_arrow` | Bézier-based arrows with head/width parameters and bends |
| ★`create_CircularArrow` | `create_circular_arrow` | elliptical arc arrow, `dir` cw/ccw |
| ★`create_Ellipse` | `create_ellipse` | |
| ★`create_Hashes` | `create_hashes` | hatching as real geometry (useful well beyond plotting) |

### Phase 5 — Plotting helpers
| R | Python | Notes |
|---|---|---|
| ★`add_Cscale` | `plot.add_colour_scale` | R's `pos='1/1'` grid-position string is a base-graphics idiom — replace with matplotlib `Axes`/`inset_axes` placement and accept `loc=` strings; document the change in `porting_notes.md` |
| ★`add_Legend` | `plot.add_legend` | 21 kB of R option-handling; simplify to a dataclass of legend options + matplotlib handles. Do not port option-by-option; port the *output*. |
| ★`add_PieLegend` | `plot.add_pie_legend` | |
| ★`add_RefGrid` | `plot.add_reference_grid` | graticule in projected space with lat/lon labels — the most valuable plotting helper; get the label placement right |
| ★`add_labels` | `plot.add_labels` | R has an interactive `mode='manual'` using `terra::click`/`utils::edit`. **Do not port interactivity.** Provide `mode='auto'` and `mode='table'` (from a label DataFrame), and document that manual placement is done by editing the table. |
| — | `plot.basemap` | new: returns `(fig, ax)` in 6932 with optional bathymetry, coastline, ASDs, reference grid and Rule-9 attribution. This is what most users will actually call. |

---

## 6. Validation gates

Faithfulness is the whole point of this port, so validation is a deliverable, not an afterthought.

**Set up first, before writing any porting code:** `tools/export_r_reference.R` runs in an R
environment with CCAMLRGIS installed and writes golden outputs into `tests/fixtures/`:
GeoPackages for every geometry-returning function under a fixed set of inputs (the package's own
example datasets plus the `My_Polygons_Form.csv` from
`geospatial_operations-main/Scripts/Polygons/`), and CSVs for tabular returns. Commit the
fixtures. If R is unavailable in this environment, say so immediately and stop — do not proceed
by eyeballing.

Comparison helper `tests/conftest.py::assert_geom_equal(py_gdf, r_gdf, tol=1e-6)`:
- same feature count, same IDs, same column names for the R-spelled data columns;
- `shapely.equals_exact` at `tol`, plus symmetric-difference area < 1e-9 × total area;
- numeric columns compared with `numpy.testing.assert_allclose(rtol=1e-9)`;
- area columns (`AreaKm2` etc.) compared at the R rounding (1 decimal).

| Gate | Must pass before starting | Criteria |
|---|---|---|
| **G0** | Phase 1 | R reference exporter runs; fixtures committed; CI green on an empty test suite |
| **G1** | Phase 2 | `project_data` round-trips to <1e-6 m; `densify_data` matches R vertex-for-vertex on: a simple box, a segment crossing the antimeridian each way, a segment exactly 180° wide (warning raised), an iso-longitude segment, and the three-polygon Building-Polygons example; `clip_to_coast` areas match to 0.1 km²; all 8 WFS loaders return non-empty 6932 layers with expected column sets |
| **G2** | Phase 3 | `create_polys/_lines/_points` match R geometry and all derived columns on the bundled examples **and** on `My_Polygons_Form.csv`; `create_polygrids` matches in both degree and equal-area modes, with equal-area cell areas within 0.1 km² of each other; `assign_areas` produces identical assignments on 1,000 random points |
| **G3** | Phase 4 | `get_depths`, `seabed_area`, `get_c_intersection`, `rotate_obj` match R; `get_iso_polys` band areas within 0.1%; `create_stations` validated distributionally — 1,000 seeds, assert every station is inside the polygon, within the depth range, respects `dist` spacing, and that the count distribution matches R's over the same number of R runs (KS test, p > 0.01) |
| **G4** | Phase 5 | Shape geometries match R; visual regression on `plot.basemap` + each `add_*` via `pytest-mpl` baselines, tolerance RMS < 5 |
| **G5** | Release | `check_geospatial_rules` passes on every layer the library produces; all four notebooks execute clean in CI; `mypy --strict` and `ruff` clean; README examples all run; `docs/porting_notes.md` lists every deviation |

Additionally, port §2 of `geospatial_operations-main/Documentation/Building_Polygons.md`
end-to-end as `notebooks/04_building_polygons.ipynb` and assert the resulting polygons match
`geospatial_operations-main/Scripts/Polygons/Completed_Polygons.gpkg`. That single test exercises
the geospatial rules, densification, projection and area computation together, and is the
strongest evidence the port is faithful to CCAMLR practice.

---

## 7. Working method

1. **Read before writing.** Start by reading `R/DensifyData.R`, `R/create.R`, `R/cPolys.R`,
   `R/cGrid.r`, `R/load.R`, `R/project_data.r`, and
   `geospatial_operations-main/Documentation/Building_Polygons.md` in full. Summarise the
   densification algorithm back in prose before implementing it.
2. **One phase per branch**, one commit per function, commit message referencing the R file and
   line range ported.
3. **Annotate heavily.** Every non-obvious block carries a comment naming the R source
   (`# CCAMLRGIS R: cPolys.R L14-L20 — ring closed by repeating first vertex`) and, where the
   Python differs, *why*. The user reads this code as documentation.
4. **Log every deviation** in `docs/porting_notes.md` as you go, with: R behaviour, Python
   behaviour, reason, and the impact on users. Known deviations to expect: stateful plotting →
   Axes-based; `add_labels` interactive mode dropped; `isoband` → matplotlib contours;
   `pos='1/1'` scale placement; bundled data → cached downloads; R recycling/partial matching
   semantics not reproduced.
5. **Ask before inventing.** If R behaviour is ambiguous (e.g. what `create_polygrids` does with
   a cell straddling the antimeridian), run the R code to find out rather than guessing. If R is
   unavailable, flag it as an open question in `porting_notes.md` instead of silently choosing.
6. **Do not "improve" numerics.** Where R rounds (`round(area/1e6, 1)`), round identically. Where
   R uses sample sd, use sample sd. Divergence must be a documented decision, never an accident.
7. **Licence hygiene.** The port is a derivative of a GPL-3 work: ship GPL-3, keep a `NOTICE`
   crediting Stephane Thanassekos, Keith Reid, Lucy Robinson, Michael D. Sumner and Roger
   Bivand, and state clearly in the README that this is an unofficial community port, not a
   CCAMLR Secretariat product, and that authoritative data remains at https://gis.ccamlr.org/
   and https://github.com/ccamlr/data.

## 8. First actions

Do these now, in order, then stop and report before writing library code:

1. Confirm both source trees are present and report the function count you find in `NAMESPACE`.
2. Report whether R + CCAMLRGIS are available in this environment (`Rscript -e 'packageVersion("CCAMLRGIS")'`).
3. Report whether `rdata`, `geopandas`, `rasterio`, `pyproj` can be installed here.
4. **Resolve the dependency set and write `environment.yml`.** Walk `NAMESPACE` and every `R/`
   file, list every R dependency actually used, map each to its Python equivalent (§3 table is
   the starting point, not the final answer — flag anything it misses), and split the result
   into: core runtime, optional extras (`plot`, `progress`), and dev-only. Then write a conda
   environment file at the repo root:
   - name `ccamlrgis-py`, **`conda-forge` as the only channel** with `channel_priority: strict` —
     mixing defaults and conda-forge is the usual cause of broken GDAL/PROJ stacks;
   - pin `python=3.11` (widest wheel coverage for the geospatial stack; the package itself
     supports ≥3.10 and CI tests 3.10–3.13);
   - install the compiled geospatial stack from conda-forge, **not pip**: `geopandas`, `shapely`,
     `pyproj`, `rasterio`, `rioxarray`, `xarray`, `gdal`, `libgdal`, `pandas`, `numpy`. Mixing
     pip and conda for GDAL-linked packages produces PROJ database version conflicts that
     surface as silent reprojection errors — exactly the failure mode this port cannot tolerate;
   - conda-forge for tooling too: `matplotlib-base` (not `matplotlib`, to skip the Qt pull-in),
     `jupyterlab`, `ipykernel`, `pytest`, `pytest-cov`, `pytest-mpl`, `mypy`, `ruff`, `requests`,
     `platformdirs`, `tqdm`, `nbval`;
   - a minimal `pip:` section only for what conda-forge lacks — check `rdata` first, it may be
     available on conda-forge; plus `-e .` so the package installs in editable mode;
   - include `r-base` and `r-sf`/`r-terra` under a **separate** `environment-r.yml` if R is
     needed here to generate the G0 golden outputs. Do not put R and Python geospatial stacks in
     one environment; they will fight over GDAL.
   Verify the file solves (`conda env create -f environment.yml --dry-run` or
   `mamba env create --dry-run`) and report the resolved versions of GDAL, PROJ and GEOS before
   moving on. Keep `environment.yml` and `pyproject.toml` dependency lists in sync, and say in
   `docs/` which is authoritative (pyproject for the published package; environment.yml for
   development and for users working in Jupyter).
5. Probe the WFS endpoints (one HEAD/GetCapabilities request) and report whether https works.
6. Propose the package name (`ccamlrgis` on PyPI if free — check) and the repo layout, flagging
   any change you want to make to §3.
7. Write `docs/r_to_python.md` with the complete mapping table, and `docs/porting_notes.md` with
   the six known deviations from §7.4 pre-filled.
