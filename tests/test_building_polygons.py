"""End-to-end test of geospatial_operations-main/Documentation/Building_Polygons.md
(design doc section 6: "the strongest evidence the port is faithful to
CCAMLR practice"). Builds three polygons from a vertex table, clips them
to the real coastline, and checks the result against
Completed_Polygons.gpkg -- the Secretariat's own committed output for
this exact worked example.

This replicates the tutorial's *manual* clipping step (st_difference
against only the "Land"-surface features of load_Coastline(), with
AreaKm2/Labx/Laby recomputed in place) rather than calling
clip_to_coast(), since that's what the tutorial itself does and what
Completed_Polygons.gpkg's column structure (no "Clipped_AreaKm2" column)
reflects.
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest

from ccamlrgis import create_polys, load_coastline
from ccamlrgis.validate import check_geospatial_rules


@pytest.mark.network
def test_building_polygons_end_to_end(fixtures):
    vertices = pd.read_csv(fixtures / "building_polygons" / "My_Polygons_Form.csv")
    expected = gpd.read_file(fixtures / "building_polygons" / "Completed_Polygons.gpkg")

    # Step 2: build densified, projected polygons
    polys = create_polys(vertices)

    # Step 3: clip to the real coastline (Land surface only), matching the
    # tutorial's manual st_difference -- not clip_to_coast()/Clip2Coast(),
    # which differences against the bundled low-res *all*-surface Coast
    # and adds a differently-named area column.
    coast = load_coastline()
    land = coast[coast["surface"] == "Land"].geometry.union_all()
    polys["geometry"] = polys.geometry.difference(land)

    # Step 4: update metadata in place, exactly as the tutorial does
    polys["AreaKm2"] = (polys.geometry.area / 1_000_000).round(1)
    centroids = polys.geometry.centroid
    polys["Labx"] = centroids.x
    polys["Laby"] = centroids.y
    polys["Reference"] = "WG-SAM-2023/xx Fig. z"

    out = polys[["ID", "AreaKm2", "Labx", "Laby", "Reference", "geometry"]]

    assert list(out["ID"]) == list(expected["ID"])
    # In practice this comes out essentially exact (AreaKm2 matches to R's
    # own rounding, Labx/Laby to ~10 significant figures, symmetric
    # difference area ~1e-12 km^2 -- floating-point noise, not drift) --
    # CCAMLR's live load_Coastline() apparently hasn't changed since
    # Completed_Polygons.gpkg was generated. Tolerances below are tight to
    # match that, not loosened defensively for an external live service.
    np.testing.assert_allclose(out["AreaKm2"], expected["AreaKm2"], atol=0.1)
    np.testing.assert_allclose(out["Labx"], expected["Labx"], rtol=1e-6)
    np.testing.assert_allclose(out["Laby"], expected["Laby"], rtol=1e-6)

    total_area = expected.geometry.area.sum()
    sym_diff_area = out.geometry.symmetric_difference(expected.geometry).area
    np.testing.assert_allclose(sym_diff_area, 0, atol=1e-6 * total_area)

    report = check_geospatial_rules(out)
    assert report.ok, report
