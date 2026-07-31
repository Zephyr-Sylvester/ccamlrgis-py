"""Cache-backed example datasets. CCAMLRGIS R: data/*.RData,
inst/extdata/SmallBathy.tif. Nothing is bundled in the wheel (design doc
section 1.3) -- these are downloaded once and cached, from a GitHub
Release asset set versioned independently of the code. See
tools/build_datasets.py for how the assets are produced.
"""

from pathlib import Path
from typing import cast

import geopandas as gpd
import pandas as pd
import rioxarray
import xarray as xr

from . import cache
from .crs import CCAMLR_CRS

DATA_VERSION = "data-v1"
_RELEASE_BASE = f"https://github.com/Zephyr-Sylvester/ccamlrgis-py/releases/download/{DATA_VERSION}"

_TABULAR = ("PolyData", "GridData", "PointData", "LineData", "PieData", "PieData2", "Labels")
_SPATIAL = ("Coast",)


def load_example(
    name: str, path: str | Path | None = None, force_refresh: bool = False
) -> pd.DataFrame | gpd.GeoDataFrame:
    """Load one of CCAMLRGIS's bundled example datasets by name:
    "PolyData", "GridData", "PointData", "LineData", "PieData", "PieData2",
    "Labels" (tabular -> `pandas.DataFrame`) or "Coast" (spatial ->
    `geopandas.GeoDataFrame`). CCAMLRGIS R: the corresponding `data/*.RData`
    object, loaded lazily with the package there; downloaded and cached
    here since nothing ships in the wheel.
    """
    if name in _TABULAR:
        url = f"{_RELEASE_BASE}/{name}.csv"
        local_path = cache.fetch(url, name=f"{name}.csv", path=path, force_refresh=force_refresh)
        return pd.read_csv(local_path)
    if name in _SPATIAL:
        url = f"{_RELEASE_BASE}/{name}.gpkg"
        local_path = cache.fetch(url, name=f"{name}.gpkg", path=path, force_refresh=force_refresh)
        return gpd.read_file(local_path).to_crs(CCAMLR_CRS)
    raise ValueError(f"Unknown example dataset {name!r}; choose from {sorted(_TABULAR + _SPATIAL)}")


def small_bathy(path: str | Path | None = None, force_refresh: bool = False) -> xr.DataArray:
    """Low-resolution (10 km) bathymetry, for illustrative purposes only --
    use `load_bathy()` for real analysis. CCAMLRGIS R: SmallBathy().
    """
    url = f"{_RELEASE_BASE}/SmallBathy.tif"
    local_path = cache.fetch(url, name="SmallBathy.tif", path=path, force_refresh=force_refresh)
    raster = cast(xr.DataArray, rioxarray.open_rasterio(local_path))
    return raster.squeeze("band", drop=True)
