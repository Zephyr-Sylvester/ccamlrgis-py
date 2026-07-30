# R → Python mapping

`ccamlrgis` (Python) ships no R-named aliases. This table is the authoritative
translation reference for CCAMLR staff porting existing R scripts by hand.
Naming rule: R `PascalCase`/`CamelCase` function and argument names become
Python `snake_case` (§1.1 of the port design). **Column names inside returned
data keep their R spellings** (`AreaKm2`, `Labx`, `Laby`, `Buffered_AreaKm2`,
`Centrelon`, `Col_<var>_<stat>`, …) — that asymmetry is intentional, see the
note at the bottom.

Status column: ✅ ported and released · 🚧 planned, not yet implemented in
this checkout (the whole library is pre-implementation as of this table's
writing — see `porting_notes.md`).

## Constants

| R | Python | Notes |
|---|---|---|
| `CCAMLRp` | `ccamlrgis.crs.CCAMLR_CRS` | EPSG:6932 constant |
| `Depth_cols` | `ccamlrgis.colours.DEPTH_COLS` | palette |
| `Depth_cuts` | `ccamlrgis.colours.DEPTH_CUTS` | palette |
| `Depth_cols2` | `ccamlrgis.colours.DEPTH_COLS2` | fishable-depth-highlighting variant |
| `Depth_cuts2` | `ccamlrgis.colours.DEPTH_CUTS2` | fishable-depth-highlighting variant |

## Load functions (`R/load.R`)

All eight take no arguments in R and return an `sf` object; all eight take no
required arguments in Python and return a `geopandas.GeoDataFrame`.

| R | Python |
|---|---|
| `load_ASDs()` | `load_asds()` |
| `load_SSRUs()` | `load_ssrus()` |
| `load_Coastline()` | `load_coastline()` |
| `load_RBs()` | `load_rbs()` |
| `load_SSMUs()` | `load_ssmus()` |
| `load_MAs()` | `load_mas()` |
| `load_MPAs()` | `load_mpas()` |
| `load_EEZs()` | `load_eezs()` |
| `load_Bathy(LocalFile, Res=5000)` | `load_bathy(path=None, res=5000)` | `LocalFile=FALSE` → `path=None`; `LocalFile="path"` → `path="path"` |
| `SmallBathy()` | `small_bathy()` | cache-backed download, not bundled |

All load functions additionally gain a Python-only `force_refresh: bool =
False` keyword (§1.3 caching contract) with no R equivalent.

## Densification (`R/DensifyData.R`)

| R | Python | Notes |
|---|---|---|
| `DensifyData(Lon, Lat, Dlon=0.1, Dlat=0.1)` | `densify_data(lon, lat, dlon=0.1, dlat=0.1)` | positional order preserved |

## Internal geometry builders (private in both languages)

| R | Python | Notes |
|---|---|---|
| `cPolys(Input, Densify=FALSE, Dlon=0.1, Dlat=0.1)` | `_build_polys(input, densify=False, dlon=0.1, dlat=0.1)` | not exported in R; private (`_`-prefixed) in Python |
| `cLines(Input, Densify=FALSE, Dlon=0.1, Dlat=0.1)` | `_build_lines(input, densify=False, dlon=0.1, dlat=0.1)` | |
| `cPoints(Input)` | `_build_points(input)` | |
| `cGrid(Input, dlon=NA, dlat=NA, Area=NA, cuts=100, cols=c('green','yellow','red'), Blank=FALSE)` | `_build_polygrid(input, dlon=None, dlat=None, area=None, cuts=100, cols=('green','yellow','red'), blank=False)` | |
| `add_buffer(Input, buf=NA, SeparateBuf=TRUE)` | `_add_buffer(input, buf=None, separate_buffers=True)` | buffer distance is nautical miles (`buf * 1852`) in both |
| `GetPerp(Input, d=Pwidth)` | `_get_perpendicular(input, d)` | arrow-width helper |

## Create functions (`R/create.R`, `R/create_*.R`, `R/Pies.R`)

| R | Python | Notes |
|---|---|---|
| `create_Polys(Input, NamesIn=NULL, Buffer=0, Densify=TRUE, Clip=FALSE, SeparateBuf=TRUE, Dlon=0.1, Dlat=0.1)` | `create_polys(input, names_in=None, buffer=0, densify=True, clip=False, separate_buffers=True, dlon=0.1, dlat=0.1)` | `densify=True` default here only |
| `create_Lines(Input, NamesIn=NULL, Buffer=0, Densify=FALSE, Clip=FALSE, SeparateBuf=TRUE, Dlon=0.1, Dlat=0.1)` | `create_lines(input, names_in=None, buffer=0, densify=False, clip=False, separate_buffers=True, dlon=0.1, dlat=0.1)` | |
| `create_Points(Input, NamesIn=NULL, Buffer=0, Clip=FALSE, SeparateBuf=TRUE)` | `create_points(input, names_in=None, buffer=0, clip=False, separate_buffers=True)` | no densify arg (R has none either) |
| `create_PolyGrids(Input, NamesIn=NULL, dlon=NA, dlat=NA, Area=NA, cuts=100, cols=c('green','yellow','red'), Blank=FALSE)` | `create_polygrids(input, names_in=None, dlon=None, dlat=None, area=None, cuts=100, cols=('green','yellow','red'), blank=False)` | two modes: degree cells vs. equal-area cells (`area=`) |
| `create_Stations(Poly, Bathy, Depths, N=NA, Nauto=NA, dist=NA, Buf=1000, ShowProgress=FALSE)` | `create_stations(poly, bathy, depths, n=None, n_auto=None, dist=None, buf=1000, progress=False)` | stochastic — Python adds `rng=`/`seed=`, absent in R |
| `create_Pies(Input, NamesIn=NULL, Classes=NULL, cols=c("green","red"), Size=50, SizeVar=NULL, GridKm=NULL, Other=0, Othercol="grey")` | `create_pies(input, names_in=None, classes=None, cols=("green","red"), size=50, size_var=None, grid_km=None, other=0, other_col="grey")` | returns geometry only; no drawing (§1.2) |
| `create_Arrow(Input, Np=50, Pwidth=5, Hlength=15, Hwidth=10, dlength=0, Atype="normal", Acol="green", Atrans=0, yx=FALSE)` | `create_arrow(input, n_points=50, pwidth=5, hlength=15, hwidth=10, dlength=0, arrow_type="normal", colour="green", alpha=0, yx=False)` | `Atrans` (0-1 base-graphics transparency) → `alpha`; colour returned as a column, not applied |
| `create_CircularArrow(Latc=-67, Lonc=-30, Lmaj=800, Lmin=500, Ang=140, Npe=100, dir="cw", ...)` | `create_circular_arrow(latc=-67, lonc=-30, lmaj=800, lmin=500, ang=140, n_points=100, direction="cw", ...)` | remaining args follow same pattern; finalise against full R signature at implementation time |
| `create_Ellipse(Latc, Lonc, Lmaj, Lmin, Ang=0, Np=100, dir="cw", yx=FALSE)` | `create_ellipse(latc, lonc, lmaj, lmin, ang=0, n_points=100, direction="cw", yx=False)` | |
| `create_Hashes(pol, angle=45, spacing=1, width=1)` | `create_hashes(polygon, angle=45, spacing=1, width=1)` | hatching as real geometry, not a plot fill |

## Analysis functions

| R | Python | Notes |
|---|---|---|
| `project_data(Input, NamesIn=NULL, NamesOut=NULL, append=TRUE, inv=FALSE)` | `project_data(input, names_in=None, names_out=None, append=True, inverse=False)` | `inv=` → `inverse=`; NA-fill/restore behaviour and "not on Earth" warnings preserved verbatim as `warnings.warn` |
| `Clip2Coast(Input)` | `clip_to_coast(input, coast)` | `coast` is required for now (temporary, see `porting_notes.md` deviation 8) — pass e.g. `load_coastline()`; a cache-backed default matching R's bundled low-res `Coast` will land once the §4 data pipeline exists |
| `assign_areas(Input, Polys, AreaNameFormat='GAR_Long_Label', Buffer=0, NamesIn=NULL, NamesOut=NULL)` | `assign_areas(input, polys, area_name_format='GAR_Long_Label', buffer=0, names_in=None, names_out=None)` | `Polys=c('ASDs','SSRUs')` (names of pre-loaded objects, looked up via R's `get()`) → `polys={'ASDs': asds, 'SSRUs': ssrus}` (a dict of the actual GeoDataFrames) — no safe Python equivalent to R's global-scope lookup; see porting_notes.md deviation 9 |
| `get_depths(Input, Bathy, NamesIn=NULL)` | `get_depths(input, bathy, names_in=None)` | |
| `seabed_area(Bathy, Poly, PolyNames=NULL, depth_classes=c(-600,-1800))` | `seabed_area(bathy, poly, poly_names=None, depth_classes=(-600, -1800))` | |
| `get_C_intersection(Line1, Line2, Plot=TRUE)` | `get_c_intersection(line1, line2)` | `Plot=` dropped — Python never draws as a side effect (§1.2); use the separate plot helper |
| `get_iso_polys(Rast, Poly=NULL, Cuts, Cols=c("green","yellow","red"), Grp=FALSE, strict=TRUE)` | `get_iso_polys(rast, poly=None, cuts, cols=("green","yellow","red"), grp=False, strict=True)` | R uses `isoband`; Python uses `matplotlib.contour`/`rasterio.features.shapes` — validate band areas within 0.1% (Gate G3) |
| `Rotate_obj(Input, Lon0=NULL)` | `rotate_obj(input, lon0=None)` | implemented as a CRS re-definition (`+lon_0=`), not a geometric affine, matching R |
| `add_col(var, cuts=100, cols=c('green','yellow','red'))` | `add_colour(var, cuts=100, cols=('green','yellow','red'))` | R name kept visible in docs per §1.1; underpins grid colouring |

## Plotting helpers (all take `ax` first, all return artists — §1.2)

| R | Python | Notes |
|---|---|---|
| — | `ccamlrgis.plot.basemap(ax=None, crs=CCAMLR_CRS, ...)` | new; no R equivalent. Returns configured `(fig, ax)` |
| `add_Cscale(pos='1/1', title='Depth (m)', width=18, height=70, ...)` | `ccamlrgis.plot.add_colour_scale(ax, title='Depth (m)', width=18, height=70, loc='lower right', ...)` | `pos='1/1'` base-graphics grid string replaced by matplotlib `loc=`/`inset_axes` placement — see `porting_notes.md` |
| `add_Legend(bb, LegOpt, Items)` | `ccamlrgis.plot.add_legend(ax, items, **options)` | R's option-handling ported by *output*, not option-by-option; `LegOpt` list becomes explicit keyword args / a dataclass |
| `add_PieLegend(Pies=NULL, bb=NULL, PosX=0, PosY=0, Size=25, lwd=1, Boxexp=c(0.2,0.2,0.12,0.3), ...)` | `ccamlrgis.plot.add_pie_legend(ax, pies=None, pos_x=0, pos_y=0, size=25, lwd=1, box_expand=(0.2,0.2,0.12,0.3), ...)` | |
| `add_RefGrid(bb, ResLat=1, ResLon=2, LabLon=NA, LatR=c(-80,-45), lwd=1, lcol="black", fontsize=1, fontcol="black", offset=NA)` | `ccamlrgis.plot.add_reference_grid(ax, res_lat=1, res_lon=2, lab_lon=None, lat_range=(-80,-45), lwd=1, line_colour="black", fontsize=1, font_colour="black", offset=None)` | |
| `add_labels(mode=NULL, layer=NULL, fontsize=1, fonttype=1, angle=0, col='black', LabelTable=NULL)` | `ccamlrgis.plot.add_labels(ax, mode='auto', layer=None, fontsize=1, fonttype=1, angle=0, colour='black', label_table=None)` | `mode='manual'` (interactive `terra::click`) **not ported**; only `mode='auto'`/`mode='table'` exist in Python |

## Data column names — kept as R spellings (deliberate asymmetry)

Function and argument names are pure `snake_case`. Column names *inside*
returned `GeoDataFrame`/`DataFrame` objects are **not** renamed, because
downstream CCAMLR workflows, published GeoPackages, and existing analysis
scripts key off the exact R spellings. Examples that stay unchanged:
`AreaKm2`, `Labx`, `Laby`, `Unbuffered_AreaKm2`, `Buffered_AreaKm2`,
`Clipped_AreaKm2`, `Buffered_and_clipped_AreaKm2`, `Centrelon`,
`Col_<var>_<stat>` (colour columns from `add_col`/`create_PolyGrids`),
`GAR_Long_Label` and the other `assign_areas` area-name-format values.
