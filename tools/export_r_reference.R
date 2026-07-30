#!/usr/bin/env Rscript
# Generates the R golden-reference fixtures that the Python test suite is
# validated against (design doc §6, gate G0/G1). Run from the repo root with
# the `ccamlrgis-r` conda env active:
#
#   conda run -n ccamlrgis-r Rscript tools/export_r_reference.R
#
# Scope of this pass: Phase 1 functions only (project_data, DensifyData,
# Clip2Coast, the 8 WFS load_* layers) -- what gate G1 needs. Phase 2+
# functions (create_Polys/_Lines/_PolyGrids, assign_areas, ...) get their own
# fixtures when that phase starts, per the "build in phases with validation
# gates" rule (design doc §1.4) -- generating fixtures for functions that
# aren't being ported yet would just be dead weight to keep in sync.

suppressMessages(suppressWarnings(library(CCAMLRGIS)))
suppressMessages(suppressWarnings(library(sf)))

if (!dir.exists("tests/fixtures")) {
  stop("Run this script from the repo root (ccamlrgis-py/); tests/fixtures/ not found here.")
}

R_VERSION <- R.version.string
CCAMLRGIS_VERSION <- as.character(packageVersion("CCAMLRGIS"))
cat(sprintf("Using %s, CCAMLRGIS %s\n", R_VERSION, CCAMLRGIS_VERSION))

manifest <- list()
sha256 <- function(path) {
  con <- file(path, "rb")
  on.exit(close(con))
  # unclass(): openssl::sha256()'s as.character() method keeps a "hash"
  # S3 class on the returned string, which jsonlite::write_json() can't
  # serialize (no asJSON method for class "sha256").
  unclass(as.character(openssl::sha256(con)))
}
record <- function(path) {
  manifest[[path]] <<- list(
    sha256 = tryCatch(sha256(path), error = function(e) NA),
    bytes = file.info(path)$size
  )
  invisible(NULL)
}

# ---------------------------------------------------------------------------
# 1. project_data
# ---------------------------------------------------------------------------
dir.create("tests/fixtures/project_data", showWarnings = FALSE, recursive = TRUE)

grid <- expand.grid(
  Lat = seq(-80, -40, by = 10),
  Lon = seq(-180, 180, by = 60)
)
edge_cases <- data.frame(
  Lat = c(NA, 100, -10),
  Lon = c(10, 10, 200)
)
fwd_input <- rbind(grid, edge_cases)
fwd_input$id <- seq_len(nrow(fwd_input))

fwd_warnings <- character(0)
fwd_out <- withCallingHandlers(
  project_data(Input = fwd_input, NamesIn = c("Lat", "Lon"), NamesOut = c("Y", "X"), append = TRUE),
  warning = function(w) {
    fwd_warnings <<- c(fwd_warnings, conditionMessage(w))
    invokeRestart("muffleWarning")
  }
)
write.csv(fwd_out, "tests/fixtures/project_data/forward.csv", row.names = FALSE)
record("tests/fixtures/project_data/forward.csv")

# Round-trip: back-project the valid (non-NA) rows
valid <- fwd_out[!is.na(fwd_out$Y) & !is.na(fwd_out$X), ]
inv_out <- project_data(Input = valid, NamesIn = c("Y", "X"), NamesOut = c("Lat2", "Lon2"), append = TRUE, inv = TRUE)
write.csv(inv_out, "tests/fixtures/project_data/inverse_roundtrip.csv", row.names = FALSE)
record("tests/fixtures/project_data/inverse_roundtrip.csv")

writeLines(fwd_warnings, "tests/fixtures/project_data/forward_warnings.txt")
record("tests/fixtures/project_data/forward_warnings.txt")

cat(sprintf("project_data: %d rows, %d warnings captured\n", nrow(fwd_out), length(fwd_warnings)))

# ---------------------------------------------------------------------------
# 2. DensifyData -- the G1 cases: simple box, antimeridian crossed each way,
#    a segment exactly 180 degrees wide (warning), an iso-longitude segment,
#    and the three Building-Polygons rings.
# ---------------------------------------------------------------------------
dir.create("tests/fixtures/densify_data", showWarnings = FALSE, recursive = TRUE)

densify_case <- function(name, lon, lat, dlon = 0.1, dlat = 0.1) {
  msgs <- character(0)
  out <- withCallingHandlers(
    CCAMLRGIS:::DensifyData(Lon = lon, Lat = lat, Dlon = dlon, Dlat = dlat),
    warning = function(w) {
      msgs <<- c(msgs, conditionMessage(w))
      invokeRestart("muffleWarning")
    }
  )
  in_df <- data.frame(Lon = lon, Lat = lat)
  out_df <- as.data.frame(out)
  write.csv(in_df, sprintf("tests/fixtures/densify_data/%s_input.csv", name), row.names = FALSE)
  write.csv(out_df, sprintf("tests/fixtures/densify_data/%s_output.csv", name), row.names = FALSE)
  record(sprintf("tests/fixtures/densify_data/%s_input.csv", name))
  record(sprintf("tests/fixtures/densify_data/%s_output.csv", name))
  list(name = name, n_in = nrow(in_df), n_out = nrow(out_df), warnings = msgs)
}

densify_results <- list()
densify_results$simple_box <- densify_case(
  "simple_box",
  lon = c(-20, -20, 0, 0, -20),
  lat = c(-60, -50, -50, -60, -60)
)
densify_results$antimeridian_ccw <- densify_case(
  "antimeridian_ccw",
  lon = c(-170, 170),
  lat = c(-65, -60)
)
densify_results$antimeridian_cw <- densify_case(
  "antimeridian_cw",
  lon = c(170, -170),
  lat = c(-60, -65)
)
densify_results$exactly_180_wide <- densify_case(
  "exactly_180_wide",
  lon = c(-90, 90),
  lat = c(-60, -60)
)
densify_results$iso_longitude <- densify_case(
  "iso_longitude",
  lon = c(-100, -100),
  lat = c(-70, -50)
)

# Building-Polygons three-ring example (geospatial_operations-main)
bp_path <- "../CCAMLRGIS-master/geospatial_operations-main/Scripts/Polygons/My_Polygons_Form.csv"
if (!file.exists(bp_path)) {
  stop("My_Polygons_Form.csv not found at ", bp_path, " -- check the CCAMLRGIS-master path")
}
bp <- read.csv(bp_path)
for (poly_id in unique(bp[, 1])) {
  ring <- bp[bp[, 1] == poly_id, ]
  # close the ring, matching cPolys.R L7-8
  ring <- rbind(ring, ring[1, ])
  densify_results[[paste0("building_polygons_", poly_id)]] <- densify_case(
    paste0("building_polygons_", poly_id),
    lon = ring[[3]],
    lat = ring[[2]]
  )
}

warnings_summary <- lapply(densify_results, function(r) list(n_in = r$n_in, n_out = r$n_out, warnings = r$warnings))
jsonlite::write_json(warnings_summary, "tests/fixtures/densify_data/summary.json", auto_unbox = TRUE, pretty = TRUE)
record("tests/fixtures/densify_data/summary.json")

for (r in densify_results) {
  cat(sprintf("densify_data[%s]: %d -> %d vertices, %d warnings\n", r$name, r$n_in, r$n_out, length(r$warnings)))
}

# ---------------------------------------------------------------------------
# 3. Clip2Coast -- uses the bundled low-res `Coast` dataset, no network.
# ---------------------------------------------------------------------------
dir.create("tests/fixtures/clip_to_coast", showWarnings = FALSE, recursive = TRUE)

clip_input <- create_Polys(PolyData, Densify = TRUE, Buffer = c(10, -15, 120))
clip_output <- Clip2Coast(clip_input)

st_write(clip_input, "tests/fixtures/clip_to_coast/input.gpkg", quiet = TRUE, append = FALSE, delete_dsn = TRUE)
st_write(clip_output, "tests/fixtures/clip_to_coast/output.gpkg", quiet = TRUE, append = FALSE, delete_dsn = TRUE)
record("tests/fixtures/clip_to_coast/input.gpkg")
record("tests/fixtures/clip_to_coast/output.gpkg")

# The exact `coast` layer Clip2Coast differenced against, so the Python port
# can be tested without needing the (not yet built) hosted-data pipeline.
st_write(Coast[Coast$ID == "All", ], "tests/fixtures/clip_to_coast/coast_all.gpkg", quiet = TRUE, append = FALSE, delete_dsn = TRUE)
record("tests/fixtures/clip_to_coast/coast_all.gpkg")

cat(sprintf(
  "clip_to_coast: %d polygons, areas (Clipped_AreaKm2 / Buffered_and_clipped_AreaKm2) recorded\n",
  nrow(clip_output)
))

# ---------------------------------------------------------------------------
# 4. load_* WFS layers -- STRUCTURAL fixtures only (column names, geometry
#    type, CRS, feature count, bbox), not full geometry. Rationale: these
#    functions fetch CCAMLR's *live, up-to-date* data by design (the R docs
#    call it "up-to-date"), so freezing exact geometry as a golden reference
#    would fight the function's own purpose and go stale the moment CCAMLR
#    edits a boundary. G1's bar for these ("non-empty 6932 layers with
#    expected column sets") is a structural check, not an equality check --
#    this fixture captures exactly that, and stays tiny (network-independent
#    tests elsewhere in the suite are unaffected; these remain
#    `pytest -m network`-only).
#
#    NB: the R package's load_*() functions hardcode http://, which now
#    returns 403 Forbidden (see PYTHON_PORT_PROMPT.md investigation). This
#    section calls the WFS endpoints directly over https instead of via
#    CCAMLRGIS::load_ASDs() etc., since the R functions themselves cannot
#    currently succeed unmodified.
# ---------------------------------------------------------------------------
dir.create("tests/fixtures/load_layers", showWarnings = FALSE, recursive = TRUE)

wfs_layers <- list(
  asds = "statistical_areas_6932",
  ssrus = "ssrus_6932",
  coastline = "coastline_v1_6932",
  rbs = "research_blocks_6932",
  ssmus = "ssmus_6932",
  mas = "omas_6932",
  mpas = "mpas_6932",
  eezs = "eez_6932"
)

fetch_layer <- function(layer_name) {
  url <- sprintf(
    "https://gis.ccamlr.org/geoserver/gis/ows?service=WFS&version=1.0.0&request=GetFeature&outputFormat=json&typeName=gis:%s",
    layer_name
  )
  d <- st_read(url, quiet = TRUE)
  st_transform(d, 6932)
}

for (nm in names(wfs_layers)) {
  cat(sprintf("Fetching %s (gis:%s)...\n", nm, wfs_layers[[nm]]))
  d <- tryCatch(fetch_layer(wfs_layers[[nm]]), error = function(e) {
    cat(sprintf("  FAILED: %s\n", conditionMessage(e)))
    NULL
  })
  if (is.null(d)) next
  bbox <- st_bbox(d)
  summary_obj <- list(
    layer = wfs_layers[[nm]],
    n_features = nrow(d),
    columns = setdiff(colnames(d), "geometry"),
    geometry_type = as.character(unique(st_geometry_type(d))),
    crs_epsg = st_crs(d)$epsg,
    bbox = as.list(bbox)
  )
  out_path <- sprintf("tests/fixtures/load_layers/%s.json", nm)
  jsonlite::write_json(summary_obj, out_path, auto_unbox = TRUE, pretty = TRUE)
  record(out_path)
  cat(sprintf("  %d features, %d columns, geometry=%s\n", nrow(d), ncol(d) - 1, summary_obj$geometry_type[1]))
}

# ---------------------------------------------------------------------------
# 5. Building-Polygons end-to-end reference (copy, not regenerate --
#    Completed_Polygons.gpkg is the Secretariat's own committed output)
# ---------------------------------------------------------------------------
dir.create("tests/fixtures/building_polygons", showWarnings = FALSE, recursive = TRUE)
bp_dir <- "../CCAMLRGIS-master/geospatial_operations-main/Scripts/Polygons"
file.copy(file.path(bp_dir, "My_Polygons_Form.csv"), "tests/fixtures/building_polygons/My_Polygons_Form.csv", overwrite = TRUE)
file.copy(file.path(bp_dir, "Completed_Polygons.gpkg"), "tests/fixtures/building_polygons/Completed_Polygons.gpkg", overwrite = TRUE)
record("tests/fixtures/building_polygons/My_Polygons_Form.csv")
record("tests/fixtures/building_polygons/Completed_Polygons.gpkg")

# ---------------------------------------------------------------------------
# 6. Phase 2 (G2): create_Polys/_Lines/_Points/_PolyGrids, add_col, assign_areas
# ---------------------------------------------------------------------------
dir.create("tests/fixtures/create_polys", showWarnings = FALSE, recursive = TRUE)
dir.create("tests/fixtures/create_lines", showWarnings = FALSE, recursive = TRUE)
dir.create("tests/fixtures/create_points", showWarnings = FALSE, recursive = TRUE)
dir.create("tests/fixtures/create_polygrids", showWarnings = FALSE, recursive = TRUE)
dir.create("tests/fixtures/add_col", showWarnings = FALSE, recursive = TRUE)
dir.create("tests/fixtures/assign_areas", showWarnings = FALSE, recursive = TRUE)
dir.create("tests/fixtures/example_data", showWarnings = FALSE, recursive = TRUE)

# Input datasets, as CSV, so the Python side can call its own port on the
# exact same input R used to produce the fixtures below.
write.csv(PolyData, "tests/fixtures/example_data/PolyData.csv", row.names = FALSE)
write.csv(LineData, "tests/fixtures/example_data/LineData.csv", row.names = FALSE)
write.csv(PointData, "tests/fixtures/example_data/PointData.csv", row.names = FALSE)
write.csv(GridData, "tests/fixtures/example_data/GridData.csv", row.names = FALSE)
record("tests/fixtures/example_data/PolyData.csv")
record("tests/fixtures/example_data/LineData.csv")
record("tests/fixtures/example_data/PointData.csv")
record("tests/fixtures/example_data/GridData.csv")

# create_Polys: default (Densify=TRUE, no buffer) on the bundled example,
# and on the Building-Polygons form (no buffer/clip -- clip_to_coast is
# already tested separately). The buffered case is already covered by the
# clip_to_coast/input.gpkg fixture (create_Polys(PolyData, Buffer=...)) --
# not duplicated here.
polys_default <- create_Polys(PolyData)
st_write(polys_default, "tests/fixtures/create_polys/polydata_default.gpkg", quiet = TRUE, append = FALSE, delete_dsn = TRUE)
record("tests/fixtures/create_polys/polydata_default.gpkg")

bp <- read.csv(bp_path)
polys_bp <- create_Polys(bp)
st_write(polys_bp, "tests/fixtures/create_polys/building_polygons.gpkg", quiet = TRUE, append = FALSE, delete_dsn = TRUE)
record("tests/fixtures/create_polys/building_polygons.gpkg")

# create_Lines: Densify=TRUE per the R docs' own example
lines_default <- create_Lines(LineData, Densify = TRUE)
st_write(lines_default, "tests/fixtures/create_lines/linedata_densify.gpkg", quiet = TRUE, append = FALSE, delete_dsn = TRUE)
record("tests/fixtures/create_lines/linedata_densify.gpkg")

# create_Points
points_default <- create_Points(PointData)
st_write(points_default, "tests/fixtures/create_points/pointdata.gpkg", quiet = TRUE, append = FALSE, delete_dsn = TRUE)
record("tests/fixtures/create_points/pointdata.gpkg")

# create_PolyGrids: degree mode (R docs' own example) and equal-area mode
grid_degree <- create_PolyGrids(GridData, dlon = 2, dlat = 1)
st_write(grid_degree, "tests/fixtures/create_polygrids/griddata_degree.gpkg", quiet = TRUE, append = FALSE, delete_dsn = TRUE)
record("tests/fixtures/create_polygrids/griddata_degree.gpkg")

grid_equalarea <- create_PolyGrids(GridData, Area = 5000)
st_write(grid_equalarea, "tests/fixtures/create_polygrids/griddata_equalarea.gpkg", quiet = TRUE, append = FALSE, delete_dsn = TRUE)
record("tests/fixtures/create_polygrids/griddata_equalarea.gpkg")

# add_col
mycols <- add_col(var = PointData$Nfishes)
write.csv(data.frame(varcol = mycols$varcol), "tests/fixtures/add_col/pointdata_nfishes_varcol.csv", row.names = FALSE)
write.csv(data.frame(cuts = mycols$cuts), "tests/fixtures/add_col/pointdata_nfishes_cuts.csv", row.names = FALSE)
write.csv(data.frame(cols = mycols$cols), "tests/fixtures/add_col/pointdata_nfishes_cols.csv", row.names = FALSE)
record("tests/fixtures/add_col/pointdata_nfishes_varcol.csv")
record("tests/fixtures/add_col/pointdata_nfishes_cuts.csv")
record("tests/fixtures/add_col/pointdata_nfishes_cols.csv")

# assign_areas: a fixed (not random -- R's RNG isn't reproducible in Python)
# set of points against the live ASDs/SSRUs layers
ASDs <- load_ASDs()
SSRUs <- load_SSRUs()
assign_input <- data.frame(
  Lat = c(-60.5, -62.2, -65.0, -67.8, -70.1, -55.3, -63.7, -58.9, -61.4, -69.2),
  Lon = c(-55.2, -45.8, -31.0, 175.3, 80.5, 10.2, -170.4, 140.7, -0.3, 100.9)
)
assigned <- assign_areas(Input = assign_input, Polys = c("ASDs", "SSRUs"), NamesOut = c("ASD", "SSRU"))
write.csv(assigned, "tests/fixtures/assign_areas/fixed_points.csv", row.names = FALSE)
record("tests/fixtures/assign_areas/fixed_points.csv")

cat(sprintf(
  "Phase 2: create_polys(%d,%d rows), create_lines(%d), create_points(%d), grids(%d,%d), assign_areas(%d)\n",
  nrow(polys_default), nrow(polys_bp), nrow(lines_default), nrow(points_default),
  nrow(grid_degree), nrow(grid_equalarea), nrow(assigned)
))

# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------
jsonlite::write_json(
  list(
    generated_with = list(r_version = R_VERSION, ccamlrgis_version = CCAMLRGIS_VERSION),
    files = manifest
  ),
  "tests/fixtures/manifest.json",
  auto_unbox = TRUE, pretty = TRUE
)

cat("Done. Fixtures written under tests/fixtures/.\n")
