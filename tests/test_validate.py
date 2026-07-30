import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

from ccamlrgis import create_polys
from ccamlrgis.crs import CCAMLR_CRS, WGS84
from ccamlrgis.validate import check_geospatial_rules


def test_create_polys_output_is_compliant(fixtures):
    """create_polys' own output should already satisfy every rule --
    densification, clockwise orientation (including the antimeridian-
    crossing polygon "two" in PolyData), and validity.
    """
    poly_data = pd.read_csv(fixtures / "example_data" / "PolyData.csv")
    polys = create_polys(poly_data)
    report = check_geospatial_rules(polys)
    assert report.ok, report


def test_building_polygons_output_is_compliant(fixtures):
    bp = pd.read_csv(fixtures / "building_polygons" / "My_Polygons_Form.csv")
    polys = create_polys(bp)
    report = check_geospatial_rules(polys)
    assert report.ok, report


def test_wrong_crs_flagged():
    gdf = gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])], crs=WGS84)
    report = check_geospatial_rules(gdf)
    assert not report.ok
    assert any(v.rule == "crs" for v in report.violations)


def test_counter_clockwise_ring_flagged():
    ccw = gpd.GeoDataFrame(
        geometry=[Polygon([(-60, -60), (-60, -60.01), (-59.99, -60.01), (-59.99, -60)])], crs=WGS84
    ).to_crs(CCAMLR_CRS)
    report = check_geospatial_rules(ccw)
    assert any(v.rule == "orientation" for v in report.violations)


def test_clockwise_ring_not_flagged():
    cw = gpd.GeoDataFrame(
        geometry=[Polygon([(-60, -60), (-59.99, -60), (-59.99, -60.01), (-60, -60.01)])], crs=WGS84
    ).to_crs(CCAMLR_CRS)
    report = check_geospatial_rules(cw)
    assert not any(v.rule == "orientation" for v in report.violations)


def test_undensified_gap_flagged():
    gdf = gpd.GeoDataFrame(geometry=[Polygon([(-60, -60), (-55, -60), (-55, -61), (-60, -61)])], crs=WGS84).to_crs(
        CCAMLR_CRS
    )
    report = check_geospatial_rules(gdf)
    assert any(v.rule == "densify" for v in report.violations)


def test_invalid_geometry_flagged():
    bowtie = gpd.GeoDataFrame(geometry=[Polygon([(-60, -60), (-59, -61), (-60, -61), (-59, -60)])], crs=CCAMLR_CRS)
    report = check_geospatial_rules(bowtie)
    assert any(v.rule == "geometry_validity" for v in report.violations)


def test_precision_check_only_runs_when_source_coords_given():
    cw = gpd.GeoDataFrame(
        geometry=[Polygon([(-60, -60), (-59.99, -60), (-59.99, -60.01), (-60, -60.01)])], crs=WGS84
    ).to_crs(CCAMLR_CRS)

    report_no_source = check_geospatial_rules(cw)
    assert not any(v.rule == "precision" for v in report_no_source.violations)

    report_with_source = check_geospatial_rules(cw, source_coords=[-60.123456, -60.1])
    assert any(v.rule == "precision" for v in report_with_source.violations)


def test_report_bool_and_repr():
    from ccamlrgis.validate import GeospatialRulesReport, Violation

    ok_report = GeospatialRulesReport()
    assert bool(ok_report) is True
    assert "ok=True" in repr(ok_report)

    bad_report = GeospatialRulesReport(violations=[Violation("crs", "wrong crs")])
    assert bool(bad_report) is False
    assert "ok=False" in repr(bad_report)
