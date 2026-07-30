# Port progress log

Tracks what's been done against `PYTHON_PORT_PROMPT.md` and what's next.
Newest entries at the top.

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
