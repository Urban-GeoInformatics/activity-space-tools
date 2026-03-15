from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import CRS
from rasterio.mask import mask
from rasterio.transform import from_origin
from scipy.spatial import cKDTree
from shapely.geometry import LineString
from shapely.ops import unary_union


@dataclass(frozen=True)
class IREMParams:
    # Boundary parameters
    home_effect_radius_m: float = 500.0
    poi_effect_radius_m: float = 100.0
    route_effect_radius_m: float = 10.0  # corridor influence for boundary construction

    # Route densification
    route_point_interval_m: float = 5.0

    # Boundary support points (stabilizes interpolation)
    boundary_point_interval_m: float = 30.0
    boundary_point_weight: float = 0.05

    # IDW raster parameters
    cell_size_m: float = 5.0
    idw_power: float = 2.0
    idw_k: int = 12
    nodata: float = 0.0

    # Output naming
    filename_prefix: str = "irem_"  # -> irem_<uniqueID>.tif


# ---------------------------------------------------------------------
# NEW FUNCTION 1: list already-produced rasters (resume / skip support)
# ---------------------------------------------------------------------
def list_existing_irem_rasters(
    out_dir: Union[str, Path],
    *,
    filename_prefix: str = "irem_",
    suffix: str = ".tif",
) -> Dict[str, Path]:
    """
    Index already-produced rasters in the output directory.

    Returns
    -------
    dict[str, Path]
        Mapping from id string -> raster path, based on filenames like:
        <filename_prefix><id><suffix>
    """
    out_dir = Path(out_dir)
    existing: Dict[str, Path] = {}
    if not out_dir.exists():
        return existing

    for p in out_dir.glob(f"{filename_prefix}*{suffix}"):
        name = p.name
        if not name.startswith(filename_prefix) or not name.endswith(suffix):
            continue
        uid = name[len(filename_prefix) : -len(suffix)]
        if uid:
            existing[uid] = p

    return existing


# ---------------------------------------------------------------------
# NEW FUNCTION 2: progress iterator (tqdm if available, else plain)
# ---------------------------------------------------------------------
def iter_with_progress(
    items: List,
    *,
    enabled: bool = True,
    desc: str = "Processing",
):
    """
    Iterate with a progress bar if tqdm is available; otherwise, plain iteration.
    """
    if not enabled:
        for it in items:
            yield it
        return

    try:
        from tqdm import tqdm  # type: ignore
    except Exception:
        for it in items:
            yield it
        return

    for it in tqdm(items, desc=desc, unit="person"):
        yield it


# ---------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------
def run_irem(
    home: gpd.GeoDataFrame,
    poi: gpd.GeoDataFrame,
    routes: gpd.GeoDataFrame,
    *,
    out_dir: Union[str, Path],
    uniqueID: str = "uniqueID",
    destinationID: str = "destinationID",
    travel_mode_col: str = "travelMode",  # stored on POI layer (optional)
    poi_weight_col: str = "weight",
    max_poi_weight: float = 30.0,
    params: IREMParams = IREMParams(),
    mode_map: Optional[dict] = None,
    default_mode: str = "motorized",
    # resume + progress + failure behavior (safe defaults)
    skip_existing: bool = True,
    show_progress: bool = True,
    continue_on_error: bool = True,
) -> list[Path]:
    """
    Run an individualized residential exposure model (IREM) and write one GeoTIFF per person.

    Required inputs
    --------------
    home : points with `uniqueID`
    poi  : points with `uniqueID`, `destinationID`, `poi_weight_col`, and (optionally) `travel_mode_col`
    routes : lines with `destinationID` (routes link POIs to their homes via destinationID join)

    Output
    ------
    Writes one raster per person into `out_dir`, named:
        <filename_prefix><id>.tif

    Resume / skip
    -------------
    If `skip_existing=True`, any person whose output file already exists in `out_dir`
    is skipped. This makes long runs restartable.

    Progress + failure reporting
    ----------------------------
    A progress bar is shown (if tqdm is installed) over individuals. The current id is printed.
    If a person fails, the id and error are printed; processing continues if `continue_on_error=True`.

    Notes on weights
    ---------------
    - POI weights are expected in [0, max_poi_weight]. Values are clamped to this range.
    - Missing POI weights are replaced with the mean of available POI weights.
    - Internally, POI weights are normalized to [0, 1].
    - Route weights inherit POI weight and are scaled by travel mode:
        walk:      factor 1.0
        bike:      factor 1/3.4
        motorized: factor 1/10

    CRS handling
    ------------
    - If inputs are not already in a projected metric CRS, all layers are reprojected to a local UTM
      CRS based on home locations.
    - Output rasters are written in that metric CRS.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _validate_inputs(
        home=home,
        poi=poi,
        routes=routes,
        uniqueID=uniqueID,
        destinationID=destinationID,
        poi_weight_col=poi_weight_col,
    )

    existing = list_existing_irem_rasters(out_dir, filename_prefix=params.filename_prefix)

    metric_crs = _resolve_metric_crs_from_home(home)

    home_m = home.to_crs(metric_crs)
    poi_m = poi.to_crs(metric_crs)
    routes_m = routes.to_crs(metric_crs)

    poi_m = _prepare_poi_weights(
        poi_m,
        poi_weight_col=poi_weight_col,
        max_poi_weight=max_poi_weight,
        out_col="w_poi",
    )

    poi_m["_mode_canon"] = _canonicalize_modes(
        poi_m,
        travel_mode_col=travel_mode_col,
        mode_map=mode_map,
        default_mode=default_mode,
    )

    boundary = _build_home_range_with_routes(
        home_m,
        poi_m,
        routes_m,
        uniqueID=uniqueID,
        destinationID=destinationID,
        params=params,
    )

    route_points = _routes_to_weighted_points(
        routes_m,
        poi_m,
        uniqueID=uniqueID,
        destinationID=destinationID,
        params=params,
    )

    # Build worklist (string ids for robust filename matching)
    boundary_ids = boundary[uniqueID].astype(str).to_numpy()
    boundary_geoms = boundary.geometry.to_numpy()

    work: List[Tuple[str, object]] = []
    skipped: List[str] = []

    for uid, geom in zip(boundary_ids, boundary_geoms):
        if geom is None or getattr(geom, "is_empty", True):
            continue
        if skip_existing and uid in existing:
            skipped.append(uid)
            continue
        work.append((uid, geom))

    written: List[Path] = []
    failed: List[Tuple[str, str]] = []

    for uid, poly in iter_with_progress(work, enabled=show_progress, desc="IREM"):
        print(f"IREM: working on {uniqueID}={uid}")

        try:
            uid_home = home_m.loc[home_m[uniqueID].astype(str) == uid, [uniqueID, "geometry"]].copy()
            uid_home["w"] = 1.0

            uid_poi = poi_m.loc[poi_m[uniqueID].astype(str) == uid, [uniqueID, "geometry", "w_poi"]].copy()
            uid_poi = uid_poi.rename(columns={"w_poi": "w"})

            uid_routes_pts = route_points.loc[
                route_points[uniqueID].astype(str) == uid, [uniqueID, "geometry", "w_route"]
            ].copy()
            uid_routes_pts = uid_routes_pts.rename(columns={"w_route": "w"})

            boundary_support = _sample_polygon_boundary_points(
                poly,
                interval=params.boundary_point_interval_m,
                weight=params.boundary_point_weight,
                crs=home_m.crs,
                uniqueID=uniqueID,
                uid_value=uid,
            )

            surface1_pts = pd.concat([uid_home, uid_poi, boundary_support], ignore_index=True)
            surface2_pts = pd.concat([uid_routes_pts, boundary_support], ignore_index=True)

            raster = _irem_surface(
                surface1_pts=surface1_pts,
                surface2_pts=surface2_pts,
                clip_polygon=poly,
                params=params,
            )

            out_path = out_dir / f"{params.filename_prefix}{uid}.tif"
            _write_clipped_geotiff(
                out_path,
                raster["array"],
                raster["transform"],
                crs=home_m.crs,
                clip_geom=poly,
                nodata=params.nodata,
            )

            written.append(out_path)

        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            failed.append((uid, msg))
            print(f"IREM: FAILED on {uniqueID}={uid} -> {msg}")
            if not continue_on_error:
                raise

    if skip_existing and skipped:
        print(f"IREM: skipped {len(skipped)} existing rasters.")

    if failed:
        print(f"IREM: {len(failed)} failures.")
        for uid, msg in failed[:10]:
            print(f"  - {uniqueID}={uid}: {msg}")
        if len(failed) > 10:
            print("  ... (more failures not shown)")

    return written


# ---------------------------------------------------------------------
# Validation and CRS helpers
# ---------------------------------------------------------------------
def _validate_inputs(
    *,
    home: gpd.GeoDataFrame,
    poi: gpd.GeoDataFrame,
    routes: gpd.GeoDataFrame,
    uniqueID: str,
    destinationID: str,
    poi_weight_col: str,
) -> None:
    for name, gdf in [("home", home), ("poi", poi), ("routes", routes)]:
        if gdf.crs is None:
            raise ValueError(f"{name} must have a defined CRS.")

    if uniqueID not in home.columns:
        raise ValueError(f"'{uniqueID}' not found in home.")
    if uniqueID not in poi.columns:
        raise ValueError(f"'{uniqueID}' not found in poi.")
    if destinationID not in poi.columns:
        raise ValueError(f"'{destinationID}' not found in poi.")
    if destinationID not in routes.columns:
        raise ValueError(f"'{destinationID}' not found in routes.")
    if poi_weight_col not in poi.columns:
        raise ValueError(f"'{poi_weight_col}' not found in poi.")

    if not home.geometry.geom_type.eq("Point").all():
        raise ValueError("home must contain only Point geometries.")
    if not poi.geometry.geom_type.eq("Point").all():
        raise ValueError("poi must contain only Point geometries.")
    if not routes.geometry.geom_type.isin(["LineString", "MultiLineString"]).all():
        raise ValueError("routes must contain LineString/MultiLineString geometries.")


def _resolve_metric_crs_from_home(home: gpd.GeoDataFrame) -> CRS:
    """
    Select a suitable local UTM CRS based on home centroid (WGS84).
    """
    home_wgs = home.to_crs(4326)
    lon = float(home_wgs.geometry.x.mean())
    lat = float(home_wgs.geometry.y.mean())
    zone = int((lon + 180) // 6) + 1
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return CRS.from_epsg(epsg)


# ---------------------------------------------------------------------
# Weight and mode utilities
# ---------------------------------------------------------------------
def _prepare_poi_weights(
    poi: gpd.GeoDataFrame,
    *,
    poi_weight_col: str,
    max_poi_weight: float,
    out_col: str,
) -> gpd.GeoDataFrame:
    maxw = float(max_poi_weight)
    if not np.isfinite(maxw) or maxw <= 0:
        raise ValueError("max_poi_weight must be a positive finite number.")

    x_raw = pd.to_numeric(poi[poi_weight_col], errors="coerce").to_numpy(dtype=float)

    finite = np.isfinite(x_raw)
    mean_val = float(np.nanmean(x_raw[finite])) if finite.any() else 0.0

    x = x_raw.copy()
    x[~np.isfinite(x)] = mean_val
    x = np.clip(x, 0.0, maxw)

    out = poi.copy()
    out[out_col] = x / maxw
    return out


def _canonicalize_modes(
    poi: gpd.GeoDataFrame,
    *,
    travel_mode_col: str,
    mode_map: Optional[dict],
    default_mode: str,
) -> pd.Series:
    """
    Map messy mode values to one of: {'walk','bike','motorized'}.
    """
    default_mode = default_mode.strip().lower()
    if default_mode not in {"walk", "bike", "motorized"}:
        raise ValueError("default_mode must be one of: 'walk', 'bike', 'motorized'.")

    if travel_mode_col not in poi.columns:
        return pd.Series([default_mode] * len(poi), index=poi.index)

    raw = poi[travel_mode_col]

    if mode_map is not None:
        mapped = raw.map(mode_map)
        out = mapped.fillna(default_mode).astype(str).str.lower()
        out = out.where(out.isin(["walk", "bike", "motorized"]), default_mode)
        return out

    s = raw.astype(str).str.strip().str.lower()

    walk_tokens = {"walk", "walking", "on foot", "foot", "kavellen"}
    bike_tokens = {"bike", "bicycle", "cycling", "cycle", "pyoralla", "pyörällä", "pyoräla", "pyorä"}
    motor_tokens = {
        "car",
        "drive",
        "driving",
        "bus",
        "tram",
        "metro",
        "train",
        "transit",
        "pt",
        "public transport",
        "motorized",
    }

    out = pd.Series([default_mode] * len(s), index=s.index)
    out = out.where(~s.isin(walk_tokens), "walk")
    out = out.where(~s.isin(bike_tokens), "bike")
    out = out.where(~s.isin(motor_tokens), "motorized")
    return out


def _mode_factor(mode: Union[str, np.ndarray]) -> np.ndarray:
    m = np.asarray(mode, dtype=str)
    m = np.char.lower(m)
    f = np.full(m.shape, 1.0 / 10.0, dtype=float)
    f[m == "walk"] = 1.0
    f[m == "bike"] = 1.0 / 3.4
    f[m == "motorized"] = 1.0 / 10.0
    return f


# ---------------------------------------------------------------------
# Boundary construction
# ---------------------------------------------------------------------
def _build_home_range_with_routes(
    home: gpd.GeoDataFrame,
    poi: gpd.GeoDataFrame,
    routes: gpd.GeoDataFrame,
    *,
    uniqueID: str,
    destinationID: str,
    params: IREMParams,
) -> gpd.GeoDataFrame:
    home_buf = home[[uniqueID, "geometry"]].copy()
    home_buf["geometry"] = home_buf.geometry.buffer(float(params.home_effect_radius_m))

    poi_buf = poi[[uniqueID, "geometry"]].copy()
    poi_buf["geometry"] = poi_buf.geometry.buffer(float(params.poi_effect_radius_m))

    routes_join = routes[[destinationID, "geometry"]].merge(
        poi[[destinationID, uniqueID]],
        on=destinationID,
        how="left",
    )
    routes_join = routes_join.dropna(subset=[uniqueID]).copy()

    routes_buf = routes_join[[uniqueID, "geometry"]].copy()
    routes_buf["geometry"] = routes_buf.geometry.buffer(float(params.route_effect_radius_m))

    uids = np.unique(
        np.concatenate(
            [
                home_buf[uniqueID].astype(str).to_numpy(),
                poi_buf[uniqueID].astype(str).to_numpy(),
                routes_buf[uniqueID].astype(str).to_numpy(),
            ]
        )
    )

    records: list[dict] = []
    for uid in uids:
        geoms = []
        geoms.extend(home_buf.loc[home_buf[uniqueID].astype(str) == uid, "geometry"].tolist())
        geoms.extend(poi_buf.loc[poi_buf[uniqueID].astype(str) == uid, "geometry"].tolist())
        geoms.extend(routes_buf.loc[routes_buf[uniqueID].astype(str) == uid, "geometry"].tolist())

        geoms = [g for g in geoms if g is not None and not g.is_empty]
        if not geoms:
            continue

        merged = unary_union(geoms)
        boundary = merged.convex_hull
        records.append({uniqueID: uid, "geometry": boundary})

    return gpd.GeoDataFrame(records, crs=home.crs)


# ---------------------------------------------------------------------
# Route densification + weights
# ---------------------------------------------------------------------
def _sample_points_along_lines(
    lines: gpd.GeoDataFrame,
    *,
    interval: float,
    keep_cols: list[str],
) -> gpd.GeoDataFrame:
    records: list[dict] = []
    for _, row in lines.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        parts = geom.geoms if geom.geom_type == "MultiLineString" else [geom]
        for seg in parts:
            length = float(seg.length)
            if length <= 0:
                continue

            dists = np.arange(interval, length, interval)
            for d in dists:
                p = seg.interpolate(float(d))
                rec = {c: row[c] for c in keep_cols}
                rec["geometry"] = p
                records.append(rec)

    return gpd.GeoDataFrame(records, crs=lines.crs)


def _routes_to_weighted_points(
    routes: gpd.GeoDataFrame,
    poi: gpd.GeoDataFrame,
    *,
    uniqueID: str,
    destinationID: str,
    params: IREMParams,
) -> gpd.GeoDataFrame:
    route_pts = _sample_points_along_lines(
        routes[[destinationID, "geometry"]],
        interval=params.route_point_interval_m,
        keep_cols=[destinationID],
    )

    join_cols = [destinationID, uniqueID, "w_poi", "_mode_canon"]
    route_pts = route_pts.merge(poi[join_cols], on=destinationID, how="left")
    route_pts = route_pts.dropna(subset=[uniqueID]).copy()

    w_poi = route_pts["w_poi"].astype(float).to_numpy()
    mf = _mode_factor(route_pts["_mode_canon"].to_numpy())

    base = np.sqrt(np.clip(w_poi, 0.0, 1.0) * 1.0)
    route_pts["w_route"] = base * mf

    return route_pts[[uniqueID, "geometry", "w_route"]].copy()


# ---------------------------------------------------------------------
# Boundary support points
# ---------------------------------------------------------------------
def _sample_polygon_boundary_points(
    poly,
    *,
    interval: float,
    weight: float,
    crs,
    uniqueID: str,
    uid_value,
) -> gpd.GeoDataFrame:
    if poly is None or poly.is_empty:
        return gpd.GeoDataFrame({uniqueID: [], "w": []}, geometry=[], crs=crs)

    rings = []
    if poly.geom_type == "Polygon":
        rings = [poly.exterior]
    else:
        rings = [p.exterior for p in poly.geoms]

    recs: list[dict] = []
    for ring in rings:
        line = LineString(ring.coords)
        length = float(line.length)
        if length <= 0:
            continue

        dists = np.arange(interval, length, interval)
        for d in dists:
            pt = line.interpolate(float(d))
            recs.append({uniqueID: uid_value, "w": float(weight), "geometry": pt})

    return gpd.GeoDataFrame(recs, crs=crs)


# ---------------------------------------------------------------------
# IDW surface + raster writing
# ---------------------------------------------------------------------
def _grid_for_polygon(poly, *, cell_size: float) -> tuple[np.ndarray, np.ndarray, rasterio.Affine]:
    minx, miny, maxx, maxy = poly.bounds
    x = np.arange(minx, maxx + cell_size, cell_size)
    y = np.arange(miny, maxy + cell_size, cell_size)
    y_desc = y[::-1]
    transform = from_origin(minx, maxy, cell_size, cell_size)
    return x, y_desc, transform


def _idw_grid(
    xy: np.ndarray,
    values: np.ndarray,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    *,
    k: int,
    power: float,
    nodata: float,
) -> np.ndarray:
    if xy.shape[0] == 0:
        return np.full((grid_y.size, grid_x.size), nodata, dtype="float32")

    tree = cKDTree(xy)
    gx, gy = np.meshgrid(grid_x, grid_y)
    targets = np.column_stack([gx.ravel(), gy.ravel()])

    kk = min(int(k), int(xy.shape[0]))
    d, idx = tree.query(targets, k=kk, workers=-1)

    if kk == 1:
        d = d[:, None]
        idx = idx[:, None]

    d = np.maximum(d, 1e-12)
    w = 1.0 / (d ** float(power))

    v = values[idx]
    z = (w * v).sum(axis=1) / w.sum(axis=1)
    return z.reshape((grid_y.size, grid_x.size)).astype("float32")


def _irem_surface(
    *,
    surface1_pts: gpd.GeoDataFrame,
    surface2_pts: gpd.GeoDataFrame,
    clip_polygon,
    params: IREMParams,
) -> dict:
    grid_x, grid_y, transform = _grid_for_polygon(clip_polygon, cell_size=float(params.cell_size_m))

    s1 = surface1_pts.dropna(subset=["w", "geometry"]).copy()
    s1_xy = np.column_stack([s1.geometry.x.to_numpy(), s1.geometry.y.to_numpy()])
    s1_v = s1["w"].astype(float).to_numpy()

    idw1 = _idw_grid(
        s1_xy,
        s1_v,
        grid_x,
        grid_y,
        k=params.idw_k,
        power=params.idw_power,
        nodata=params.nodata,
    )

    s2 = surface2_pts.dropna(subset=["w", "geometry"]).copy()
    if len(s2) == 0:
        summed = idw1
    else:
        s2_xy = np.column_stack([s2.geometry.x.to_numpy(), s2.geometry.y.to_numpy()])
        s2_v = s2["w"].astype(float).to_numpy()
        idw2 = _idw_grid(
            s2_xy,
            s2_v,
            grid_x,
            grid_y,
            k=params.idw_k,
            power=params.idw_power,
            nodata=params.nodata,
        )
        summed = (idw1 + idw2).astype("float32")

    return {"array": summed, "transform": transform}


def _write_clipped_geotiff(
    path: Path,
    array: np.ndarray,
    transform: rasterio.Affine,
    *,
    crs: CRS,
    clip_geom,
    nodata: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    height, width = array.shape
    meta = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": array.dtype,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
        "compress": "deflate",
        "tiled": True,
    }

    tmp = path.with_suffix(".tmp.tif")
    with rasterio.open(tmp, "w", **meta) as dst:
        dst.write(array, 1)

    with rasterio.open(tmp) as src:
        out_image, out_transform = mask(src, [clip_geom], crop=True, nodata=nodata)
        out_meta = src.meta.copy()
        out_meta.update(
            {
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
            }
        )

    with rasterio.open(path, "w", **out_meta) as dst:
        dst.write(out_image)

    tmp.unlink(missing_ok=True)