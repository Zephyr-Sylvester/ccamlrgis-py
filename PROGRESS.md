# Port progress log

Tracks what's been done against `PYTHON_PORT_PROMPT.md` and what's next.
Newest entries at the top.

## 2026-07-29 (5) — Phase 3: get_depths, seabed_area, get_c_intersection, get_iso_polys, rotate_obj

### Done

- `load_bathy` (load.py) now returns an `xarray.DataArray` with the `.rio`
  accessor via `rioxarray.open_rasterio()`, not a raw `rasterio` handle --
  fixes a deviation from the design doc's own §3 (rasters should be
  xarray) that had crept in during Phase 1 before Phase 3 needed a real
  raster representation to build on. Added `rioxarray`/`xarray` to
  `pyproject.toml` (already in `environment.yml`).
- `rotate_obj`, `get_c_intersection`, `get_depths`, `seabed_area`,
  `get_iso_polys` all implemented in `analysis.py`, validated against G3
  fixtures generated the same way as G0-G2. Since `small_bathy()`/the
  cache-backed bundled-data pipeline (§4) still doesn't exist, sourced a
  local test-only copy of R's bundled `SmallBathy.tif` directly (same
  pattern as `coast_all.gpkg` for `clip_to_coast` earlier) -- this is a
  `tests/fixtures/` file, not shipped in the package.
- **41/41 tests pass** (32 offline + 9 network).
- Found and fixed a real bug empirically: `seabed_area`'s and
  `get_iso_polys`'s raster clipping needed `all_touched=True` and `=False`
  respectively to match R's `terra::mask()` -- confirmed by testing both
  settings against real R output for each function rather than assuming
  rioxarray's default matches. `all_touched=False` (rioxarray's default)
  alone was undercounting `seabed_area` by several percent on every
  non-trivial stratum.
- Two new deviations logged (`porting_notes.md` 11-12): `seabed_area` has
  a small (~1-2%) residual on the deepest/open-ended depth stratum, likely
  GDAL-vs-terra sub-pixel tie-breaking; `get_iso_polys` uses blocky
  raster-cell-edge polygons (`rasterio.features.shapes` on a classified
  array) instead of R's `isoband`-smooth interpolated contours -- total
  area matches closely (0.3% in testing) but individual thin/edge bands
  can diverge up to ~25%. A follow-up could switch to `contourpy` (which
  matplotlib itself now uses internally, no plotting backend required) for
  closer fidelity; not done this round to avoid a new dependency.

### Scope not covered this round (by design)

- `create_stations` -- the last Phase 3 function, deliberately deferred.
  It's stochastic (needs its own `rng=`/`seed=` design) and the design
  doc's own G3 gate calls for *distributional* validation (1,000 seeds,
  KS test against R's own distribution over many runs), which is a
  meaningfully different and larger validation task than the
  fixture-equality approach used for everything else so far -- better
  scoped as its own round than rushed alongside five other functions.

### Next

1. `create_stations`, with its distributional validation harness.
2. GitHub Actions CI.
3. `datasets.py` + §4 data-publishing pipeline.
4. Phase 4: shapes and pies (`create_pies`, `create_arrow`,
   `create_circular_arrow`, `create_ellipse`, `create_hashes`).

## 2026-07-29 (4) — Phase 2: create_polys/_lines/_points/_polygrids, add_colour, assign_areas

### Done

All of Phase 2 (§5's "Create functions" table) is implemented in
`src/ccamlrgis/create.py` (`create_polys`, `create_lines`, `create_points`,
`create_polygrids` -- both degree and equal-area modes, plus the private
`_build_polys`/`_build_lines`/`_build_points`/`_add_buffer` builders),
`src/ccamlrgis/colours.py` (`add_colour`), and `assign_areas` (added to
`analysis.py`). Extended `tools/export_r_reference.R` with G2 fixtures
(reusing the existing `clip_to_coast/input.gpkg` fixture for the buffered
`create_polys` case rather than duplicating it) and added the R example
datasets (`PolyData`/`LineData`/`PointData`/`GridData`) as CSVs so the
Python side can call the same input R used. **33/33 tests pass** (24
offline + 9 network).

Real bugs found and fixed while validating against fixtures (not
R-behaviour deviations -- these are correctness fixes, logged here rather
than in porting_notes.md):
- `_add_buffer` used shapely's default buffer resolution (16 segments/circle)
  vs sf's default `nQuadSegs=30` (120/circle) -- visible geometry mismatch
  on any positive buffer. Fixed by passing `resolution=30`.
- Line length used a WGS84 ellipsoidal geodesic (pyproj default), but R's
  `st_length()` on geographic coordinates uses **s2** (spherical, IUGG mean
  radius 6371.01 km) by default -- a systematic ~0.3-0.6% length error.
  Fixed by using a sphere of that radius instead of the WGS84 ellipsoid.
- `_seq_inclusive` (the "densify a cell edge to 0.1 degree steps" helper)
  could overshoot the upper bound, unlike R's `seq()` -- silently producing
  a longitude > 180 near the antimeridian and corrupting a cell polygon.
  Fixed to match R's exact stop-at-or-before-`to` semantics.
- `create_polygrids`'s point-to-cell merge conflated the spatial index's
  *positional* match (0-based) with the cell's `ID` *value* (1-based),
  silently dropping exactly one populated cell from every non-blank grid.
  Fixed by mapping through `group["ID"]` instead of assuming
  `position == ID - 1`.

Two new deviations logged (`porting_notes.md` 9-10): `assign_areas` takes
`polys` as a dict of GeoDataFrames instead of R's `Polys=c('name',...)` +
`get()`-from-caller's-global-scope (no safe Python equivalent); the
boundary-point nudge in grid point-matching is deterministic instead of
R's random coin-flip (not a meaningful faithfulness target either way).

`add_colour`'s hex output can differ from R's by ±1 in a single RGB channel
at rounding boundaries -- explicitly allowed by the design doc's own
faithfulness bar ("cosmetic plotting output need not be pixel-identical").

### Next

1. GitHub Actions CI.
2. `datasets.py` + §4 data-publishing pipeline (unblocks `clip_to_coast`'s
   default `coast=`, `small_bathy()`, bundled example datasets).
3. Phase 3: `get_depths`, `seabed_area`, `get_c_intersection`, `rotate_obj`,
   `get_iso_polys`, `create_stations` (validated distributionally, not by
   equality -- it's stochastic).

## 2026-07-29 (3) — cache.py, load.py, clip_to_coast

### Done

- `src/ccamlrgis/cache.py`: download-on-demand cache per §1.3 (explicit
  `path=` > `CCAMLRGIS_CACHE_DIR` env var > platformdirs), conditional
  requests (ETag/If-Modified-Since), atomic write, `manifest.json` with
  SHA-256, `CCAMLRGISOfflineError`, `prefetch()`, `info()`. Kept lean: no
  retry logic or progress bars yet (progress is a separate optional-extra
  concern per §3, not needed for correctness).
- `src/ccamlrgis/load.py`: all 8 WFS loaders (`load_asds` ... `load_eezs`)
  plus `load_bathy`, all over https (R's hardcoded http 403s, see the
  2026-07-29 (1) entry below).
- `clip_to_coast` added to `analysis.py`. Deviation: `coast` is a required
  argument for now rather than defaulting to a cache-backed low-res `Coast`
  fetch, since that needs the §4 data-publishing pipeline (GitHub Release
  assets), which doesn't exist yet — logged as porting_notes.md deviation 8.
- Extended `tools/export_r_reference.R` to also export the exact `Coast`
  row (`ID=='All'`) that R's `Clip2Coast` differenced against, so
  `clip_to_coast` could be tested end-to-end without needing that pipeline.
- Tests: `test_cache.py` (offline, mocked HTTP), `test_clip_to_coast.py`
  (against the new fixture), `test_load.py` (`pytest -m network`, structural
  checks against `tests/fixtures/load_layers/*.json` — not exact-geometry,
  since these functions fetch CCAMLR's live data by design). **24/24 tests
  pass** (16 offline + 8 live network, run against the real WFS today).

### Next

1. GitHub Actions CI (single Python version on ubuntu to start).
2. `datasets.py` + §4 data-publishing pipeline (unblocks `clip_to_coast`'s
   default `coast=`, `small_bathy()`, and the bundled example datasets).
3. Phase 2: `_build_polys`/`_build_lines`/`_build_points`, `create_polys`
   etc., validated against new G2 fixtures.

## 2026-07-29 (2) — Phase 1 implementation: project_data, densify_data

### Done

- `pyproject.toml` (hatchling, src layout) and minimal `README.md`.
- `src/ccamlrgis/`: `crs.py` (`CCAMLR_CRS`/`WGS84` constants), `analysis.py`
  (`project_data`), `densify.py` (`densify_data`). Both ported functions
  pass their full G1 fixture suite (`tests/test_project_data.py`,
  `tests/test_densify.py`, 11 tests) against real R output.
- Built the real `ccamlrgis-py` conda dev env (not just dry-run solved) and
  did an editable install; both work.
- Found and fixed a real bug while validating `densify_data` against
  fixtures: manually-added segment endpoints and computed grid-line
  intersections that land on the same coordinate weren't deduplicating
  (Python float equality is bit-exact; needed round-before-dedup at 9
  decimals). Also found and documented a genuine R quirk (not a port bug):
  R itself emits an exact-duplicate consecutive vertex on some
  antimeridian-crossing segments (float noise in its own GEOS pipeline) —
  logged as `porting_notes.md` deviation 7; the G1 test collapses R's
  consecutive duplicates before comparing rather than requiring raw
  vertex-count equality.

### Scope not covered this round (by design, for efficiency)

- `load_*` WFS loaders, `clip_to_coast`, `small_bathy` — all need
  `cache.py` (download/cache/manifest per §1.3) and, for `clip_to_coast`
  specifically, a sourced copy of the `Coast` dataset. That's a separate,
  larger unit of work (cache module + eventual GitHub Release data
  pipeline from §4), deliberately deferred rather than half-built alongside
  this round's two functions.
- No CI yet.
- `cPolys`/`cLines`/`cPoints`/`create_Polys` etc. (Phase 2) not started.

### Next

1. `cache.py` (§1.3), then `load.py` (8 WFS wrappers) and `clip_to_coast`
   (needs a locally-sourced `Coast` copy for now, ahead of the real data
   pipeline).
2. GitHub Actions CI (start with one Python version on ubuntu; expand to
   the full matrix later — no need to gold-plate before there's more code
   to test).
3. Phase 2: `_build_polys`/`_build_lines`/`_build_points`, `create_polys`
   etc., validated against new G2 fixtures generated the same way as G0/G1.

## 2026-07-29 — §8 first actions + G0 golden fixtures

### Done

**Environment investigation (§8.1-8.3, 8.5-8.6):**
- Both source trees confirmed present: `~/repos/CCAMLRGIS-master` (R package,
  34 exported functions per `NAMESPACE`, 4,851 lines across 28 `R/` files)
  and its `geospatial_operations-main/` subdirectory.
- System R (4.1.2) had neither CCAMLRGIS nor its compiled deps (sf, terra,
  lwgeom, bezier) installed, and was old enough to risk CRAN binary
  incompatibility — did not treat this as "R unavailable"; built a separate
  conda-forge R environment instead (see below).
- System `pip` is externally-managed (Homebrew Python) and refuses installs;
  `conda`/`mamba` (miniforge3) work and are the intended toolchain.
- WFS endpoints: **https now works** (200 on GetCapabilities); **http
  returns 403 Forbidden**, not a redirect — the R package's `load_*()`
  functions hardcode `http://` and can no longer succeed unmodified. Python
  port must default to https; the R package itself is stale here.
- Package name `ccamlrgis` confirmed free on PyPI. No `r-ccamlrgis`
  conda-forge feedstock exists (expected — CRAN-only).

**Environments (§8.4):**
- `environment.yml` (Python, `ccamlrgis-py`) written and **dry-run solved
  successfully**: Python 3.11.15, GDAL 3.12.3, PROJ 9.7.1, GEOS 3.14.1, 339
  packages. `rdata` (pure-Python `.RData` reader) confirmed on conda-forge,
  included as a core dep rather than a pip fallback.
- `environment-r.yml` (R-only, `ccamlrgis-r`, for G0 golden-output
  generation) written, built, and **CCAMLRGIS 4.3.1 installed from CRAN**
  into it and verified loadable. Note: had to relax the R pin from `=4.3` to
  `>=4.4` — conda-forge's `r-lwgeom` builds require R ≥4.4; solver picked
  R 4.5.3.

**Docs (§8.7):**
- `docs/r_to_python.md` — complete function + argument mapping for all 34
  exported functions plus the internal helpers, with the "column names keep
  R spelling" asymmetry called out explicitly.
- `docs/porting_notes.md` — the six known deviations from §7.4, pre-filled
  (stateful plotting → Axes-based; `add_labels` manual mode dropped;
  `isoband` → matplotlib/rasterio; `pos='1/1'` → `loc=`; bundled data →
  cache-backed downloads; R recycling/partial-matching not reproduced).

**Densification algorithm (§7.1)** — read `DensifyData.R`, `create.R`,
`cPolys.R`, `cGrid.r`, `load.R`, `project_data.r`, and
`Building_Polygons.md` in full; summarized in conversation. Two-pass
algorithm: (1) fix antimeridian crossings by splitting a wrapping segment
into two at an interpolated crossing latitude, using a `+360°`-shifted
helper segment to find it; (2) densify each non-wrapping segment against a
local `Dlon×Dlat` graticule via line intersection + `st_line_project`
re-ordering. Confirmed `sf_use_s2(FALSE)` has no shapely-2 equivalent
needed (shapely is always planar) — just needs a comment. Confirmed from
`cPolys.R` that the densify *trigger* is a hardcoded 0.1° max-|Δlon|
threshold independent of the user's `Dlon` — only the grid *resolution* is
user-configurable.

**G0 golden fixtures** — `tools/export_r_reference.R` written and run
against real CCAMLRGIS 4.3.1 (in `ccamlrgis-r`), producing 580 KB under
`tests/fixtures/`:
- `project_data/` — forward + inverse round-trip on a 35-point lat/lon grid
  plus NA/out-of-range edge cases, with R's exact warning text captured.
- `densify_data/` — all five G1 cases (simple box, antimeridian crossed
  both directions, exactly-180°-wide segment with its warning,
  iso-longitude segment) plus the three Building-Polygons rings (P1/P2/P3),
  each as input/output CSV pairs + `summary.json`.
- `clip_to_coast/` — input/output GeoPackages from
  `create_Polys(PolyData, Buffer=c(10,-15,120)) → Clip2Coast()` (uses the
  bundled low-res `Coast`, no network).
- `load_layers/` — **structural** JSON (feature count, columns, geometry
  type, CRS, bbox) for all 8 WFS layers, fetched directly over https
  (bypassing the R package's broken http-hardcoded functions). Deliberately
  not full-geometry fixtures: these functions fetch CCAMLR's live data by
  design, so freezing exact geometry would go stale and fight the
  function's purpose. G1's bar ("non-empty 6932 layers with expected column
  sets") is a structural check, which this covers.
- `building_polygons/` — copy of `My_Polygons_Form.csv` and
  `Completed_Polygons.gpkg` for the eventual end-to-end notebook test.
- `manifest.json` — SHA-256 + byte size for every fixture file, R/CCAMLRGIS
  version used to generate them.

Scope note: this is a **Phase 1** fixture set (what gate G1 needs), not all
34 functions. Phase 2+ fixtures (`create_Polys`/`_Lines`/`_PolyGrids`,
`assign_areas`, ...) get generated when that phase starts, per the
build-in-phases rule (§1.4) — generating fixtures now for functions not yet
being ported would just be dead weight to keep in sync as R's own output
(or our understanding of it) evolves.

### Not done yet

- No `pyproject.toml` / `src/ccamlrgis/` — no library code has been written.
  This was an explicit stop point per the initial instruction ("stop before
  writing library code"); resuming now means Phase 1 implementation is next.
- No CI. G0's full bar ("CI green on an empty test suite") isn't met yet —
  there's no test suite or GitHub Actions config to be green. That's part of
  Phase 1 scaffolding.
- No GitHub remote yet — this is a local-only git repo for now.
- Phase 2+ fixtures (create/analysis functions) not generated.
- `load_Bathy`/`SmallBathy` raster fixtures deferred to Phase 3
  (`get_depths`, `seabed_area`, `create_Stations` need them; Phase 1 doesn't).

### Next

1. Scaffold `pyproject.toml` (hatchling backend, deps synced with
   `environment.yml`), `src/ccamlrgis/` package skeleton, `py.typed`.
2. Implement Phase 1: `crs.py` (the `CCAMLR_CRS` constant), `cache.py`
   (download/cache/manifest/prefetch per §1.3), `project_data`,
   `densify_data`, the 8 `load_*` WFS wrappers (https), `small_bathy`/
   `datasets.load_example`.
3. Write `tests/conftest.py::assert_geom_equal` and the G1 test suite against
   the fixtures already committed.
4. Stand up GitHub Actions (3.10-3.13 × ubuntu/macos/windows matrix) so G0's
   "CI green on an empty test suite" — then G1 — can actually be checked.
5. Push to a GitHub remote once the user creates one.
