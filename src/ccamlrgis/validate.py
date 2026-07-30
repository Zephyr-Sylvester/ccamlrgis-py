"""Geospatial rules compliance checking. CCAMLR's geospatial rules
(geospatial_operations-main/README.md), endorsed by the Scientific
Committee in 2023 (SC-CAMLR-42, para 2.30), encoded as code per the
design doc's own instruction (section 2) rather than left as prose only.

Checks covered: CRS is EPSG:6932 (rule 1); no un-densified segment exceeds
`dlon` degrees of longitude (rule 2); polygon exterior rings are clockwise
in geographic coordinates (rule 3); geometry validity. Coordinate
precision (rule 3's "at least five decimals") is checked only if
`source_coords` -- the original lon/lat input, before projection -- is
supplied, since the projected/densified output geometry in a GeoDataFrame
doesn't itself carry that information.
"""

from dataclasses import dataclass, field

import numpy as np
from shapely.validation import explain_validity

from .crs import WGS84


@dataclass
class Violation:
    rule: str
    message: str
    index: int | None = None


@dataclass
class GeospatialRulesReport:
    violations: list = field(default_factory=list)

    @property
    def ok(self):
        return len(self.violations) == 0

    def __bool__(self):
        return self.ok

    def __repr__(self):
        if self.ok:
            return "GeospatialRulesReport(ok=True, 0 violations)"
        lines = "\n".join(f"  [{v.rule}] row {v.index}: {v.message}" for v in self.violations)
        return f"GeospatialRulesReport(ok=False, {len(self.violations)} violations):\n{lines}"


def _iter_rings(geom):
    """Yield an (n, 2) lon/lat coordinate array for every ring/line in `geom`."""
    gt = geom.geom_type
    if gt == "Polygon":
        yield np.array(geom.exterior.coords)
        for interior in geom.interiors:
            yield np.array(interior.coords)
    elif gt == "LineString":
        yield np.array(geom.coords)
    elif gt in ("MultiPolygon", "MultiLineString", "GeometryCollection"):
        for part in geom.geoms:
            yield from _iter_rings(part)
    elif gt == "Point":
        return
    elif hasattr(geom, "coords"):
        yield np.array(geom.coords)


def _max_lon_gap(coords):
    """Max angular longitude distance between consecutive vertices,
    antimeridian-aware -- same formula as densify_data.
    """
    if len(coords) < 2:
        return 0.0
    lon = coords[:, 0]
    diffs = np.abs(((np.diff(lon) + 180) % 360) - 180)
    return float(diffs.max())


def _ring_signed_area(coords):
    """Shoelace signed area of a closed ring (first point == last point).
    Negative = clockwise, positive = counter-clockwise, in the standard
    x-right/y-up plane (lon=x, lat=y).

    Longitude is unwrapped across +/-180 first: a ring that legitimately
    crosses the antimeridian (e.g. create_polys densifies straight through
    it) has raw longitude values that jump from ~180 to ~-180 between
    consecutive vertices, which -- left as-is -- makes the shoelace formula
    misjudge the winding direction entirely.
    """
    x = np.unwrap(coords[:, 0], period=360)
    y = coords[:, 1]
    return 0.5 * float(np.sum(x[:-1] * y[1:] - x[1:] * y[:-1]))


def _count_decimals(value):
    s = f"{value:.10f}".rstrip("0")
    return len(s.split(".")[1]) if "." in s else 0


def check_geospatial_rules(gdf, dlon=0.1, check_orientation=True, source_coords=None):
    """Check a GeoDataFrame against CCAMLR's geospatial rules. Returns a
    `GeospatialRulesReport` (truthy iff there are no violations).

    `source_coords`, if given, is an array-like of raw decimal-degree
    values (e.g. the original Lat/Lon columns of the input a `create_*`
    function was called with) checked for >=5 decimal places (rule 3);
    without it, that specific check is skipped rather than silently
    passed.
    """
    violations = []

    if gdf.crs is None or gdf.crs.to_epsg() != 6932:
        violations.append(Violation("crs", f"CRS is {gdf.crs}, expected EPSG:6932"))

    for idx, geom in gdf.geometry.items():
        if geom is None or geom.is_empty:
            continue
        if not geom.is_valid:
            violations.append(Violation("geometry_validity", explain_validity(geom), index=idx))

    try:
        gdf_wgs84 = gdf.to_crs(WGS84)
    except Exception as exc:
        violations.append(Violation("crs", f"could not reproject to WGS84 to check densification/orientation: {exc}"))
        gdf_wgs84 = None

    if gdf_wgs84 is not None:
        for idx, geom in gdf_wgs84.geometry.items():
            if geom is None or geom.is_empty:
                continue

            for ring in _iter_rings(geom):
                gap = _max_lon_gap(ring)
                # small float tolerance: a segment densified at exactly
                # `dlon` spacing can compute to e.g. 0.1000000000000001
                # after the projected round-trip through EPSG:6932 and
                # back, which is not a real rule violation.
                if gap > dlon + 1e-9:
                    violations.append(
                        Violation("densify", f"segment spans {gap:.3f} degrees of longitude (> {dlon})", index=idx)
                    )

            if check_orientation and geom.geom_type in ("Polygon", "MultiPolygon"):
                polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
                for poly in polys:
                    coords = np.array(poly.exterior.coords)
                    if len(coords) >= 4 and _ring_signed_area(coords) > 0:
                        violations.append(
                            Violation(
                                "orientation",
                                "exterior ring is counter-clockwise; CCAMLR rule 3 requires clockwise",
                                index=idx,
                            )
                        )

    if source_coords is not None:
        for i, value in enumerate(np.asarray(source_coords, dtype=float).ravel()):
            decimals = _count_decimals(value)
            if decimals < 5:
                violations.append(
                    Violation(
                        "precision",
                        f"coordinate {value} has only {decimals} decimal place(s), rule requires >=5",
                        index=i,
                    )
                )

    return GeospatialRulesReport(violations=violations)
