"""WFS layer loaders. CCAMLRGIS R: load.R. The R functions hardcode
http://, which now returns 403 Forbidden from CCAMLR's server (confirmed
2026-07-29); this port uses https throughout.
"""

from pathlib import Path
from typing import cast

import geopandas as gpd
import rioxarray
import xarray as xr

from . import cache
from .cite import LAYER_INFO, WFS_URL_TEMPLATE, layer_citation
from .crs import CCAMLR_CRS

_BATHY_URL = "https://gis.ccamlr.org/geoserver/www/GEBCO2024_{res}.tif"
_VALID_BATHY_RES = (500, 1000, 2500, 5000)


def _load_wfs_layer(key: str, path: str | Path | None = None, force_refresh: bool = False) -> gpd.GeoDataFrame:
    _, type_name = LAYER_INFO[key]
    url = WFS_URL_TEMPLATE.format(type_name=type_name)
    local_path = cache.fetch(url, name=f"{type_name}.json", path=path, force_refresh=force_refresh)
    gdf = gpd.read_file(local_path).to_crs(CCAMLR_CRS)
    # Rule 8: every loaded layer carries its own citation (design doc section 2).
    gdf.attrs["citation"] = layer_citation(key)
    return gdf


def load_asds(path: str | Path | None = None, force_refresh: bool = False) -> gpd.GeoDataFrame:
    """CCAMLR Statistical Areas, Subareas and Divisions. CCAMLRGIS R: load_ASDs."""
    return _load_wfs_layer("asds", path=path, force_refresh=force_refresh)


def load_ssrus(path: str | Path | None = None, force_refresh: bool = False) -> gpd.GeoDataFrame:
    """CCAMLR Small Scale Research Units. CCAMLRGIS R: load_SSRUs."""
    return _load_wfs_layer("ssrus", path=path, force_refresh=force_refresh)


def load_coastline(path: str | Path | None = None, force_refresh: bool = False) -> gpd.GeoDataFrame:
    """Full CCAMLR coastline (UK Polar Data Centre/BAS + Natural Earth). CCAMLRGIS R: load_Coastline."""
    return _load_wfs_layer("coastline", path=path, force_refresh=force_refresh)


def load_rbs(path: str | Path | None = None, force_refresh: bool = False) -> gpd.GeoDataFrame:
    """CCAMLR Research Blocks. CCAMLRGIS R: load_RBs."""
    return _load_wfs_layer("rbs", path=path, force_refresh=force_refresh)


def load_ssmus(path: str | Path | None = None, force_refresh: bool = False) -> gpd.GeoDataFrame:
    """CCAMLR Small Scale Management Units. CCAMLRGIS R: load_SSMUs."""
    return _load_wfs_layer("ssmus", path=path, force_refresh=force_refresh)


def load_mas(path: str | Path | None = None, force_refresh: bool = False) -> gpd.GeoDataFrame:
    """CCAMLR Management Areas. CCAMLRGIS R: load_MAs."""
    return _load_wfs_layer("mas", path=path, force_refresh=force_refresh)


def load_mpas(path: str | Path | None = None, force_refresh: bool = False) -> gpd.GeoDataFrame:
    """CCAMLR Marine Protected Areas. CCAMLRGIS R: load_MPAs."""
    return _load_wfs_layer("mpas", path=path, force_refresh=force_refresh)


def load_eezs(path: str | Path | None = None, force_refresh: bool = False) -> gpd.GeoDataFrame:
    """Exclusive Economic Zones. CCAMLRGIS R: load_EEZs."""
    return _load_wfs_layer("eezs", path=path, force_refresh=force_refresh)


def load_bathy(res: int = 5000, path: str | Path | None = None, force_refresh: bool = False) -> xr.DataArray:
    """GEBCO 2024 bathymetry, reprojected to the CCAMLR CRS by CCAMLR.
    CCAMLRGIS R: load_Bathy (``LocalFile=FALSE`` -> always cache-backed here;
    there is no local-file passthrough mode in the port -- pass ``path=`` to
    point the cache itself at an existing directory instead).

    Returns an ``xarray.DataArray`` with the ``.rio`` accessor (design doc
    section 3: rasters are xarray, not raw rasterio handles), single-band
    bathymetry squeezed to 2D (y, x).
    """
    if res not in _VALID_BATHY_RES:
        raise ValueError(f"'res' should be one of {_VALID_BATHY_RES}")
    url = _BATHY_URL.format(res=res)
    local_path = cache.fetch(url, name=f"GEBCO2024_{res}.tif", path=path, force_refresh=force_refresh, timeout=3600)
    raster = cast(xr.DataArray, rioxarray.open_rasterio(local_path))
    return raster.squeeze("band", drop=True)
