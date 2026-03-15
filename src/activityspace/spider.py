from __future__ import annotations

from typing import Literal, Optional, Union

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS


DuplicateHomePolicy = Literal["error", "first", "mean"]
MetricCRS = Union[Literal["auto"], int, str, CRS]


def add_distance_to_home(
    poi: gpd.GeoDataFrame,
    home: gpd.GeoDataFrame,
    *,
    uniqueID: str,
    home_key: Optional[str] = None,
    distance_col: str = "dist_m",
    metric_crs: MetricCRS = "auto",
    keep_original_crs: bool = True,
    duplicate_home_policy: DuplicateHomePolicy = "error",
    missing_value: float = np.nan,
) -> gpd.GeoDataFrame:
    """
    Add distance-to-home in meters.

    - Handles mismatched CRS automatically.
    - Computes distance in a projected CRS with meter units.
    - Returns geometry in the original POI CRS by default.

    If `metric_crs="auto"`, a local UTM CRS is selected from POI location.
    """

    hk = uniqueID if home_key is None else home_key
    _validate_inputs(poi=poi, home=home, uniqueID=uniqueID, home_key=hk)

    original_crs = poi.crs
    metric_crs_resolved = _resolve_metric_crs(poi=poi, metric_crs=metric_crs)

    poi_m = poi.to_crs(metric_crs_resolved)
    home_m = home.to_crs(metric_crs_resolved)

    home_xy = _build_home_xy_table(
        home=home_m,
        home_key=hk,
        duplicate_home_policy=duplicate_home_policy,
    )

    out = poi_m.copy()
    out = out.join(home_xy, on=uniqueID)

    missing = out["home_x"].isna() | out["home_y"].isna()
    dx = out.geometry.x - out["home_x"]
    dy = out.geometry.y - out["home_y"]

    out[distance_col] = np.sqrt(dx**2 + dy**2)
    out.loc[missing, distance_col] = missing_value

    out = out.drop(columns=["home_x", "home_y"])

    if keep_original_crs:
        out = out.to_crs(original_crs)

    return out


def _validate_inputs(*, poi: gpd.GeoDataFrame, home: gpd.GeoDataFrame, uniqueID: str, home_key: str) -> None:
    if poi.crs is None or home.crs is None:
        raise ValueError("Both inputs must have a defined CRS.")
    if uniqueID not in poi.columns:
        raise ValueError(f"POI key '{uniqueID}' not found.")
    if home_key not in home.columns:
        raise ValueError(f"Home key '{home_key}' not found.")
    if not poi.geometry.geom_type.eq("Point").all():
        raise ValueError("POI dataset must contain only Point geometries.")
    if not home.geometry.geom_type.eq("Point").all():
        raise ValueError("Home dataset must contain only Point geometries.")


def _resolve_metric_crs(*, poi: gpd.GeoDataFrame, metric_crs: MetricCRS) -> CRS:
    if metric_crs != "auto":
        crs = CRS.from_user_input(metric_crs)
        if crs.is_geographic:
            raise ValueError("metric_crs must be projected (meter-based), not geographic.")
        return crs

    # Auto-select local UTM based on POI centroid
    poi_wgs = poi.to_crs(4326)
    lon = float(poi_wgs.geometry.x.mean())
    lat = float(poi_wgs.geometry.y.mean())

    zone = int((lon + 180) // 6) + 1
    epsg = 32600 + zone if lat >= 0 else 32700 + zone

    return CRS.from_epsg(epsg)


def _build_home_xy_table(
    *,
    home: gpd.GeoDataFrame,
    home_key: str,
    duplicate_home_policy: DuplicateHomePolicy,
) -> pd.DataFrame:
    tbl = home[[home_key]].copy()
    tbl["home_x"] = home.geometry.x.to_numpy()
    tbl["home_y"] = home.geometry.y.to_numpy()

    dup_mask = tbl[home_key].duplicated(keep=False)
    if not dup_mask.any():
        return tbl.set_index(home_key)

    if duplicate_home_policy == "error":
        dup_keys = tbl.loc[dup_mask, home_key].unique()
        preview = ", ".join(map(str, dup_keys[:5]))
        raise ValueError(
            f"Duplicate keys found in home '{home_key}'. Examples: {preview}. "
            f"Use duplicate_home_policy='first' or 'mean'."
        )

    if duplicate_home_policy == "first":
        return tbl.drop_duplicates(subset=[home_key], keep="first").set_index(home_key)

    if duplicate_home_policy == "mean":
        return tbl.groupby(home_key, as_index=True)[["home_x", "home_y"]].mean()

    raise ValueError(f"Unknown duplicate_home_policy: {duplicate_home_policy}")