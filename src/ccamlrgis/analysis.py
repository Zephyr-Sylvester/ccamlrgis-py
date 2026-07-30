import warnings

import numpy as np
import pandas as pd
from pyproj import Transformer

from .crs import CCAMLR_CRS, WGS84

_FORWARD = Transformer.from_crs(WGS84, CCAMLR_CRS, always_xy=True)
_INVERSE = Transformer.from_crs(CCAMLR_CRS, WGS84, always_xy=True)


def project_data(input, names_in=None, names_out=None, append=True, inverse=False):
    """Project Lat/Lon to the CCAMLR CRS (or back-project Y/X to Lat/Lon).
    CCAMLRGIS R: project_data.r. ``names_in``/``names_out`` follow R's
    convention: [Lat-like name, Lon-like name] (Y/lat first, X/lon second).
    """
    df = pd.DataFrame(input).reset_index(drop=True)

    if names_in is None:
        raise ValueError("'names_in' not specified")
    if len(names_in) != 2:
        raise ValueError("'names_in' should be a sequence of length 2")
    if any(n not in df.columns for n in names_in):
        raise ValueError("'names_in' do not match column names in 'input'")

    if names_out is None:
        names_out = ["Latitude", "Longitude"] if inverse else ["Y", "X"]

    lat_name, lon_name = names_in[0], names_in[1]
    # locs columns: [x-like, y-like] i.e. [Lon, Lat] or [X, Y]
    locs = df[[lon_name, lat_name]].to_numpy(dtype=float)

    missing = np.isnan(locs).any(axis=1)
    n_missing = int(missing.sum())
    if n_missing == 1:
        warnings.warn("One record is missing location and will not be projected\n")
    elif n_missing > 1:
        warnings.warn(f"{n_missing} records are missing location and will not be projected\n")

    if not inverse:
        impossible = (
            (locs[:, 0] > 180) | (locs[:, 0] < -180) | (locs[:, 1] > 90) | (locs[:, 1] < -90)
        )
        n_impossible = int(impossible.sum())
        if n_impossible == 1:
            warnings.warn("One record is not on Earth and will not be projected\n")
        elif n_impossible > 1:
            warnings.warn(f"{n_impossible} records are not on Earth and will not be projected\n")
        locs[impossible] = np.nan
    else:
        impossible = np.zeros(len(df), dtype=bool)

    fill = missing | impossible
    locs_filled = locs.copy()
    locs_filled[fill] = [0.0, -60.0]

    transformer = _INVERSE if inverse else _FORWARD
    x, y = transformer.transform(locs_filled[:, 0], locs_filled[:, 1])

    out = pd.DataFrame({names_out[1]: x, names_out[0]: y})[list(names_out)]
    out.loc[fill, :] = np.nan

    if append:
        return pd.concat([df, out], axis=1)
    return out


def clip_to_coast(input, coast):
    """Clip polygons to a coastline, removing the land portion, and record
    the resulting area. CCAMLRGIS R: Clip2Coast.R.

    Unlike R (which defaults to a bundled low-res ``Coast`` dataset),
    ``coast`` must be supplied explicitly for now -- e.g. the output of
    ``load_coastline()`` -- since that bundled dataset isn't hosted yet via
    the cache pipeline (see porting_notes.md). ``coast`` may be any
    GeoDataFrame/GeoSeries of land polygons; all of its geometries are
    unioned before differencing.
    """
    land = coast.geometry.union_all() if hasattr(coast, "geometry") else coast.union_all()
    output = input.copy()
    output["geometry"] = output.geometry.difference(land)
    area = (output.geometry.area / 1_000_000).round(1)
    if "Buffered_AreaKm2" in output.columns:
        output["Buffered_and_clipped_AreaKm2"] = area
    if "AreaKm2" in output.columns:
        output["Clipped_AreaKm2"] = area
    return output
