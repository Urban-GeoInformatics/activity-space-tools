from __future__ import annotations

import warnings
from typing import Optional

import geopandas as gpd
import numpy as np
from shapely.ops import unary_union

from .spider import add_distance_to_home


def model_home_range(
    poi: gpd.GeoDataFrame,
    home: gpd.GeoDataFrame,
    *,
    uniqueID: str = "uniqueID",
    home_effect_radius_m: float = 500.0,
    poi_effect_radius_m: float = 100.0,
    filter_far_pois: bool = False,
    max_poi_distance_m: Optional[float] = None,
    keep_fields: Optional[list[str]] = None,
) -> gpd.GeoDataFrame:
    """
    Model an individualized home range boundary from home and activity locations.

    The home range boundary reflects:
      - an immediate home effect radius (D1) around home locations, and
      - a local area-of-effect around activity locations (fuzziness/uncertainty).

    Optionally, activity locations can be filtered by distance-to-home (meters).
    When filtering is enabled, distance-to-home is computed internally.

    Parameters
    ----------
    poi : geopandas.GeoDataFrame
        Activity locations (points).
    home : geopandas.GeoDataFrame
        Home locations (points).
    uniqueID : str, default="uniqueID"
        Column identifying individuals in both datasets.
    home_effect_radius_m : float, default=500.0
        Immediate home effect radius (D1), in meters (in a metric CRS).
    poi_effect_radius_m : float, default=100.0
        Area-of-effect radius around activity locations, in meters (in a metric CRS).
    filter_far_pois : bool, default=False
        If True, exclude POIs farther than `max_poi_distance_m` from home.
    max_poi_distance_m : float or None
        Maximum allowed POI distance from home (meters) when filtering is enabled.
    keep_fields : list[str] or None
        Optional fields to copy from the home dataset into the output.

    Returns
    -------
    geopandas.GeoDataFrame
        One polygon per individual representing the modeled home range boundary.
    """
    _validate_inputs(poi=poi, home=home, uniqueID=uniqueID)

    poi_use = poi.copy()

    if filter_far_pois:
        if max_poi_distance_m is None:
            raise ValueError("max_poi_distance_m must be provided when filter_far_pois=True.")

        warnings.warn(
            "Distance-to-home is computed internally using duplicate_home_policy='first'. "
            "Ensure duplicate home identifiers do not affect your results.",
            UserWarning,
            stacklevel=2,
        )

        poi_use = add_distance_to_home(
            poi_use,
            home,
            uniqueID=uniqueID,
            duplicate_home_policy="first",
        )

        poi_use = poi_use.loc[
            poi_use["dist_m"].astype(float) <= float(max_poi_distance_m)
        ].copy()

    home_buf = home.copy()
    home_buf["geometry"] = home_buf.geometry.buffer(float(home_effect_radius_m))

    poi_buf = poi_use.copy()
    poi_buf["geometry"] = poi_buf.geometry.buffer(float(poi_effect_radius_m))

    ids = _unique_union(home_buf[uniqueID], poi_buf[uniqueID])

    records: list[dict] = []

    for uid in ids:
        geoms = []
        geoms.extend(home_buf.loc[home_buf[uniqueID] == uid, "geometry"].tolist())
        geoms.extend(poi_buf.loc[poi_buf[uniqueID] == uid, "geometry"].tolist())

        geoms = [g for g in geoms if g is not None and not g.is_empty]
        if not geoms:
            continue

        merged = unary_union(geoms)
        boundary = merged.convex_hull  # method implementation detail

        rec = {uniqueID: uid, "geometry": boundary}

        if keep_fields:
            row = home.loc[home[uniqueID] == uid]
            if not row.empty:
                for f in keep_fields:
                    if f in row.columns:
                        rec[f] = row.iloc[0][f]

        records.append(rec)

    out = gpd.GeoDataFrame(records, crs=home.crs)
    out = out.loc[out.geometry.notna() & ~out.geometry.is_empty].copy()
    return out


def _validate_inputs(*, poi: gpd.GeoDataFrame, home: gpd.GeoDataFrame, uniqueID: str) -> None:
    if poi.crs is None or home.crs is None:
        raise ValueError("Both inputs must have a defined CRS.")
    if uniqueID not in poi.columns:
        raise ValueError(f"'{uniqueID}' not found in POI.")
    if uniqueID not in home.columns:
        raise ValueError(f"'{uniqueID}' not found in home.")
    if not poi.geometry.geom_type.eq("Point").all():
        raise ValueError("POI must contain only Point geometries.")
    if not home.geometry.geom_type.eq("Point").all():
        raise ValueError("Home must contain only Point geometries.")


def _unique_union(a, b) -> np.ndarray:
    av = np.asarray(a)
    bv = np.asarray(b)
    if av.size == 0:
        return np.unique(bv)
    if bv.size == 0:
        return np.unique(av)
    return np.unique(np.concatenate([av, bv]))