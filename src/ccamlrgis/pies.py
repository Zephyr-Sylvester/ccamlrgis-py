import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from .analysis import project_data
from .colours import _ramp_palette
from .crs import CCAMLR_CRS


def create_pies(
    input,
    names_in=None,
    classes=None,
    cols=("green", "red"),
    size=50,
    size_var=None,
    grid_km=None,
    other=0,
    other_col="grey",
):
    """Pie-chart polygons for overlaying on a map: one pie per location,
    slices sized by each class's share of the total. CCAMLRGIS R: Pies.R
    (create_Pies). Returns a GeoDataFrame with a `col` colour column --
    geometry only, never drawn (design doc section 1.2).
    """
    df = pd.DataFrame(input).copy()
    if names_in is None:
        raise ValueError("'names_in' not specified")
    if len(names_in) != 4:
        raise ValueError("'names_in' should be a sequence of length 4")
    if any(n not in df.columns for n in names_in):
        raise ValueError("'names_in' do not match column names in 'input'")

    names_in = list(names_in)
    if size_var is not None:
        if size_var not in df.columns:
            raise ValueError("'size_var' does not match any column name in 'input'")
        if size_var not in names_in:
            names_in = [*names_in, size_var]

    d = df[names_in].copy()
    if len(names_in) == 4:
        d.columns = ["Lat", "Lon", "Cl", "N"]
    else:
        d.columns = ["Lat", "Lon", "Cl", "N", "SizeVar"]
        if d.groupby(["Lat", "Lon"])["SizeVar"].nunique().max() != 1:
            raise ValueError("Some location(s) have more than one 'size_var'")

    if classes is None:
        classes = sorted(d["Cl"].unique())
    else:
        classes = list(classes)
        classes_in_data = sorted(d["Cl"].unique())
        if not all(c in classes for c in classes_in_data):
            excl = [c for c in classes_in_data if c not in classes]
            d.loc[d["Cl"].isin(excl), "Cl"] = "Other"

    if grid_km is not None:
        gr = grid_km * 1000
        locs = project_data(d, names_in=["Lat", "Lon"], append=True)

        def _snap(vals):
            edges = np.arange(gr * np.floor((vals.min() - gr) / gr), gr * np.ceil((vals.max() + gr) / gr) + gr, gr)
            idx = np.clip(np.digitize(vals, edges, right=False) - 1, 0, len(edges) - 2)
            return edges[idx] + gr / 2

        locs["Xc"] = _snap(locs["X"].to_numpy())
        locs["Yc"] = _snap(locs["Y"].to_numpy())
        back = project_data(locs, names_in=["Yc", "Xc"], names_out=["Latitude", "Longitude"], inverse=True, append=True)
        d["Lat"], d["Lon"] = back["Latitude"], back["Longitude"]

        if "SizeVar" not in d.columns:
            d = d.groupby(["Lat", "Lon", "Cl"], as_index=False)["N"].sum()
        else:
            svar_by_loc = d[["Lat", "Lon", "SizeVar"]].drop_duplicates()
            gridded_locs = back[["Lat", "Lon", "Latitude", "Longitude"]].drop_duplicates()
            svar_by_loc = svar_by_loc.merge(gridded_locs, on=["Lat", "Lon"])
            svar_sum = svar_by_loc.groupby(["Latitude", "Longitude"], as_index=False)["SizeVar"].sum()
            svar_sum = svar_sum.rename(columns={"Latitude": "Lat", "Longitude": "Lon"})
            d = d.groupby(["Lat", "Lon", "Cl"], as_index=False)["N"].sum()
            d = d.merge(svar_sum, on=["Lat", "Lon"], how="left")

    tot = d.groupby(["Lat", "Lon"], as_index=False)["N"].sum().rename(columns={"N": "Tot"})
    tot["ID"] = np.arange(1, len(tot) + 1)
    d = d.merge(tot, on=["Lat", "Lon"], how="left")
    if size_var is not None and size_var == names_in[3]:
        d["SizeVar"] = d["Tot"]

    d["p"] = d["N"] / d["Tot"]
    if other > 0:
        d.loc[100 * d["p"] < other, "Cl"] = "Other"

    group_cols = ["ID", "Lat", "Lon", "Cl"]
    agg = {"N": "sum", "Tot": "first", "p": "sum"}
    if "SizeVar" in d.columns:
        agg["SizeVar"] = "first"
    d = d.groupby(group_cols, as_index=False).agg(agg)

    cols_ramp = _ramp_palette(cols, len(classes))
    if "Other" in d["Cl"].values and "Other" not in classes:
        classes = [*list(classes), "Other"]
        cols_ramp = [*cols_ramp, *_ramp_palette([other_col], 1)]

    class_index = {c: i for i, c in enumerate(classes)}
    d["col"] = [cols_ramp[class_index[c]] for c in d["Cl"]]
    d = project_data(d, names_in=["Lat", "Lon"])

    d["Area"] = size * 1e10
    if "SizeVar" in d.columns:
        d["Area"] = d["Area"] * d["SizeVar"] / d["SizeVar"].unique().mean()
    d["R"] = np.sqrt(d["Area"] / np.pi)
    d["PolID"] = np.arange(1, len(d) + 1)
    d["LegT"] = None
    d["Leg"] = None
    d.iloc[0, d.columns.get_loc("LegT")] = "Classes"
    d.iloc[0, d.columns.get_loc("Leg")] = ";".join(classes)
    d.iloc[1, d.columns.get_loc("LegT")] = "cols"
    d.iloc[1, d.columns.get_loc("Leg")] = ";".join(cols_ramp)

    polygons = {}
    for pie_id in d["ID"].unique():
        dat = d[d["ID"] == pie_id].copy()
        dat["_order"] = dat["Cl"].map(class_index)
        dat = dat.sort_values("_order").reset_index(drop=True)
        cx, cy = dat["X"].iloc[0], dat["Y"].iloc[0]
        r = dat["R"].iloc[0]
        ang = 2 * np.pi * dat["p"].to_numpy()
        edges = np.concatenate([[0], np.cumsum(ang)])
        starts, ends = edges[:-1], edges[1:]

        for j in range(len(dat)):
            pol_id = dat["PolID"].iloc[j]
            a = np.array([starts[j], ends[j]])
            if a[1] - a[0] > 0.1:
                a = np.sort(np.unique(np.concatenate([a, np.arange(a[0], a[1], 0.1)])))
            if dat["p"].iloc[j] == 1:
                a = np.append(a, 0.0)
                x = cx + r * np.sin(a)
                y = cy + r * np.cos(a)
            else:
                x = np.concatenate([[cx], cx + r * np.sin(a), [cx]])
                y = np.concatenate([[cy], cy + r * np.cos(a), [cy]])
            polygons[pol_id] = Polygon(np.column_stack([x, y]))

    d["geometry"] = d["PolID"].map(polygons)
    out = gpd.GeoDataFrame(d, geometry="geometry", crs=CCAMLR_CRS)
    if out["R"].nunique() > 1:
        out = out.sort_values("R", ascending=False).reset_index(drop=True)
    return out
