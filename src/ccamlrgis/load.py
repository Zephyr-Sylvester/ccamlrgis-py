"""WFS layer loaders. CCAMLRGIS R: load.R. The R functions hardcode
http://, which now returns 403 Forbidden from CCAMLR's server (confirmed
2026-07-29); this port uses https throughout.
"""

import geopandas as gpd
import rioxarray

from . import cache
from .crs import CCAMLR_CRS

_WFS_URL = (
    "https://gis.ccamlr.org/geoserver/gis/ows?service=WFS&version=1.0.0"
    "&request=GetFeature&outputFormat=json&typeName=gis:{layer}"
)
_BATHY_URL = "https://gis.ccamlr.org/geoserver/www/GEBCO2024_{res}.tif"
_VALID_BATHY_RES = (500, 1000, 2500, 5000)


def _load_wfs_layer(layer, path=None, force_refresh=False):
    url = _WFS_URL.format(layer=layer)
    local_path = cache.fetch(url, name=f"{layer}.json", path=path, force_refresh=force_refresh)
    gdf = gpd.read_file(local_path)
    return gdf.to_crs(CCAMLR_CRS)


def load_asds(path=None, force_refresh=False):
    """CCAMLR Statistical Areas, Subareas and Divisions. CCAMLRGIS R: load_ASDs."""
    return _load_wfs_layer("statistical_areas_6932", path=path, force_refresh=force_refresh)


def load_ssrus(path=None, force_refresh=False):
    """CCAMLR Small Scale Research Units. CCAMLRGIS R: load_SSRUs."""
    return _load_wfs_layer("ssrus_6932", path=path, force_refresh=force_refresh)


def load_coastline(path=None, force_refresh=False):
    """Full CCAMLR coastline (UK Polar Data Centre/BAS + Natural Earth). CCAMLRGIS R: load_Coastline."""
    return _load_wfs_layer("coastline_v1_6932", path=path, force_refresh=force_refresh)


def load_rbs(path=None, force_refresh=False):
    """CCAMLR Research Blocks. CCAMLRGIS R: load_RBs."""
    return _load_wfs_layer("research_blocks_6932", path=path, force_refresh=force_refresh)


def load_ssmus(path=None, force_refresh=False):
    """CCAMLR Small Scale Management Units. CCAMLRGIS R: load_SSMUs."""
    return _load_wfs_layer("ssmus_6932", path=path, force_refresh=force_refresh)


def load_mas(path=None, force_refresh=False):
    """CCAMLR Management Areas. CCAMLRGIS R: load_MAs."""
    return _load_wfs_layer("omas_6932", path=path, force_refresh=force_refresh)


def load_mpas(path=None, force_refresh=False):
    """CCAMLR Marine Protected Areas. CCAMLRGIS R: load_MPAs."""
    return _load_wfs_layer("mpas_6932", path=path, force_refresh=force_refresh)


def load_eezs(path=None, force_refresh=False):
    """Exclusive Economic Zones. CCAMLRGIS R: load_EEZs."""
    return _load_wfs_layer("eez_6932", path=path, force_refresh=force_refresh)


def load_bathy(res=5000, path=None, force_refresh=False):
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
    return rioxarray.open_rasterio(local_path).squeeze("band", drop=True)
