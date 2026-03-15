from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from pyproj import CRS
from rasterio.warp import reproject, Resampling
from rasterio.features import shapes
from shapely.geometry import shape
from shapely.ops import unary_union


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _parse_id_from_filename(path: Path, *, filename_prefix: str) -> str:
    """
    Extract ID from a filename like: <prefix><ID>.tif
    Example: irem_A01.tif -> A01
    """
    name = path.name
    if not name.startswith(filename_prefix):
        raise ValueError(f"Raster name does not start with prefix '{filename_prefix}': {name}")
    stem = path.stem
    uid = stem[len(filename_prefix):]
    if uid == "":
        raise ValueError(f"Could not parse ID from raster name: {name}")
    return uid


def _list_rasters(
    raster_dir: Union[str, Path],
    *,
    filename_prefix: str = "irem_",
    suffix: str = ".tif",
) -> list[Path]:
    raster_dir = Path(raster_dir)
    if not raster_dir.exists():
        raise FileNotFoundError(f"Raster directory not found: {raster_dir}")
    return sorted(raster_dir.glob(f"{filename_prefix}*{suffix}"))


def _read_raster_as_array(
    path: Path,
    *,
    nodata_to: float = 0.0,
) -> Tuple[np.ndarray, dict]:
    """
    Read band 1 into a float32 array. Replace nodata with nodata_to.
    Returns (array, profile_subset).
    """
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32", copy=False)
        nodata = src.nodata
        profile = {
            "crs": src.crs,
            "transform": src.transform,
            "width": src.width,
            "height": src.height,
            "nodata": nodata,
        }

    if nodata is not None:
        arr = np.where(arr == nodata, float(nodata_to), arr)

    arr = np.nan_to_num(arr, nan=float(nodata_to))
    return arr, profile


def _ensure_same_grid(a_profile: dict, b_profile: dict) -> None:
    """
    Raise if rasters are not aligned (same CRS, shape, transform).
    """
    if a_profile["crs"] != b_profile["crs"]:
        raise ValueError("CRS mismatch between rasters.")
    if a_profile["width"] != b_profile["width"] or a_profile["height"] != b_profile["height"]:
        raise ValueError("Shape mismatch between rasters.")
    if a_profile["transform"] != b_profile["transform"]:
        raise ValueError("Transform mismatch between rasters (different grid alignment).")


def _reproject_match(
    src_path: Path,
    target_profile: dict,
    *,
    nodata_to: float = 0.0,
    resampling: Resampling = Resampling.nearest,
) -> np.ndarray:
    """
    Reproject/resample src raster to match target grid. Returns float32 array.
    """
    with rasterio.open(src_path) as src:
        src_arr = src.read(1).astype("float32", copy=False)
        src_nodata = src.nodata
        if src_nodata is not None:
            src_arr = np.where(src_arr == src_nodata, float(nodata_to), src_arr)
        src_arr = np.nan_to_num(src_arr, nan=float(nodata_to))

        dst = np.full(
            (target_profile["height"], target_profile["width"]),
            float(nodata_to),
            dtype="float32",
        )

        reproject(
            source=src_arr,
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=target_profile["transform"],
            dst_crs=target_profile["crs"],
            resampling=resampling,
        )

    return dst


def _resolve_local_metric_crs(gdf: gpd.GeoDataFrame) -> CRS:
    """
    Choose a suitable local UTM CRS based on dataset center (WGS84).
    Ensures metric units for geometry calculations.

    Uses representative_point() to avoid centroid warnings on geographic CRS.
    """
    if gdf.crs is None:
        raise ValueError("Input GeoDataFrame must have a defined CRS.")

    gdf_wgs = gdf.to_crs(4326)

    # representative_point is always within geometry and avoids centroid warnings
    rp = gdf_wgs.geometry.representative_point()
    lon = float(rp.x.mean())
    lat = float(rp.y.mean())

    zone = int((lon + 180) // 6) + 1
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return CRS.from_epsg(epsg)


# ---------------------------------------------------------------------
# 1) Raster summaries for a folder (mean + total)
# ---------------------------------------------------------------------

def summarize_rasters(
    raster_dir: Union[str, Path],
    *,
    filename_prefix: str = "irem_",
    nodata_to: float = 0.0,
) -> pd.DataFrame:
    """
    Compute per-raster mean and total (sum of all pixels), returning a table.

    Returns columns:
      - uniqueID (string)
      - raster_path
      - mean
      - total
    """
    paths = _list_rasters(raster_dir, filename_prefix=filename_prefix)

    rows = []
    for p in paths:
        uid = _parse_id_from_filename(p, filename_prefix=filename_prefix)
        arr, _profile = _read_raster_as_array(p, nodata_to=nodata_to)
        rows.append(
            {
                "uniqueID": str(uid),
                "raster_path": str(p),
                "mean": float(arr.mean()),
                "total": float(arr.sum()),
            }
        )

    return pd.DataFrame(rows)


def exposure_summary(
    gdf: gpd.GeoDataFrame,
    raster_dir: Union[str, Path],
    *,
    uniqueID: str = "uniqueID",
    filename_prefix: str = "irem_",
    mean_col: str = "avg_exp",
    total_col: str = "total_exp",
    nodata_to: float = 0.0,
) -> gpd.GeoDataFrame:
    """
    Join raster summary stats (mean + total) onto a GeoDataFrame by uniqueID.
    """
    if uniqueID not in gdf.columns:
        raise ValueError(f"'{uniqueID}' not found in gdf.")

    stats = summarize_rasters(raster_dir, filename_prefix=filename_prefix, nodata_to=nodata_to)
    stats = stats.rename(columns={"mean": mean_col, "total": total_col})

    out = gdf.copy()
    out["_join_id"] = out[uniqueID].astype(str)
    stats["_join_id"] = stats["uniqueID"].astype(str)

    out = out.merge(stats[["_join_id", mean_col, total_col]], on="_join_id", how="left")
    out = out.drop(columns=["_join_id"])
    return out


# ---------------------------------------------------------------------
# 2) Geometry calculator for polygons (meters regardless of input CRS)
# ---------------------------------------------------------------------

def as_geometry_calculator(
    polygons: gpd.GeoDataFrame,
    *,
    uniqueID: str = "uniqueID",
    elongation_col: str = "elong",
    orientation_col: str = "orient",
    area_col: str = "area_m2",
    perimeter_col: str = "perim_m",
    zero_width_value: float = 99099.0,
) -> gpd.GeoDataFrame:
    """
    Add geometry-based metrics for each polygon.

    Metrics are computed in meters regardless of input CRS by projecting internally
    to a suitable local metric CRS (UTM chosen automatically).

    Adds:
      - elongation: length/width from minimum rotated rectangle (>= 1)
      - orient: long-axis angle in degrees, normalized to [-90, 90]
      - area_m2: polygon area in square meters
      - perim_m: polygon perimeter in meters

    Returns a new GeoDataFrame in the original CRS.
    """
    if polygons.crs is None:
        raise ValueError("Input GeoDataFrame must have a defined CRS.")
    if uniqueID not in polygons.columns:
        raise ValueError(f"'{uniqueID}' not found in polygons.")
    if not polygons.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Input must contain Polygon/MultiPolygon geometries.")

    metric_crs = _resolve_local_metric_crs(polygons)
    poly_m = polygons.to_crs(metric_crs)

    def _measure(geom) -> Tuple[float, float]:
        if geom is None or geom.is_empty:
            return (np.nan, np.nan)

        rect = geom.minimum_rotated_rectangle
        coords = list(rect.exterior.coords)

        edges = []
        for i in range(4):
            x1, y1 = coords[i]
            x2, y2 = coords[i + 1]
            dx = x2 - x1
            dy = y2 - y1
            length = float(np.hypot(dx, dy))
            edges.append((length, dx, dy))

        lengths = sorted([e[0] for e in edges], reverse=True)
        L = lengths[0]
        W = lengths[2]  # rectangle edge lengths repeat

        elg = float(zero_width_value) if W == 0 else float(L / W)

        long_edge = max(edges, key=lambda t: t[0])
        dx, dy = long_edge[1], long_edge[2]
        ang = float(np.degrees(np.arctan2(dy, dx)))

        while ang > 90:
            ang -= 180
        while ang < -90:
            ang += 180

        return elg, ang

    out = polygons.copy()
    out[area_col] = poly_m.geometry.area.astype(float)
    out[perimeter_col] = poly_m.geometry.length.astype(float)

    vals = poly_m.geometry.apply(_measure)
    out[elongation_col] = vals.apply(lambda t: t[0])
    out[orientation_col] = vals.apply(lambda t: t[1])

    return out


# ---------------------------------------------------------------------
# 3) Landtype exposure from IREM rasters folder
# ---------------------------------------------------------------------

def compute_landtype_exposure(
    irem_raster_dir: Union[str, Path],
    landtype_raster: Union[str, Path],
    *,
    label: str,
    filename_prefix: str = "irem_",
    nodata_to: float = 0.0,
    auto_align_landtype: bool = False,
    resampling: Resampling = Resampling.nearest,
) -> pd.DataFrame:
    """
    For each IREM raster in a folder, compute:
      product = IREM * LANDTYPE
    Then:
      - total exposure: sum(product)
      - average exposure: mean(product)

    landtype_raster can be:
      - a binary mask (0/1)
      - or continuous intensity

    If auto_align_landtype=True, landtype is reprojected/resampled to match each IREM raster.
    Otherwise, landtype and IREM must already match grid exactly.
    """
    irem_paths = _list_rasters(irem_raster_dir, filename_prefix=filename_prefix)
    landtype_raster = Path(landtype_raster)

    rows = []
    for p in irem_paths:
        uid = _parse_id_from_filename(p, filename_prefix=filename_prefix)

        irem_arr, irem_profile = _read_raster_as_array(p, nodata_to=nodata_to)

        if auto_align_landtype:
            land_arr = _reproject_match(
                landtype_raster,
                irem_profile,
                nodata_to=nodata_to,
                resampling=resampling,
            )
        else:
            land_arr, land_profile = _read_raster_as_array(landtype_raster, nodata_to=nodata_to)
            _ensure_same_grid(irem_profile, land_profile)

        prod = irem_arr * land_arr
        rows.append(
            {
                "uniqueID": str(uid),
                "raster_path": str(p),
                f"{label}_exp": float(prod.sum()),
                f"{label}_exAVG": float(prod.mean()),
            }
        )

    return pd.DataFrame(rows)


def attach_landtype_exposure(
    gdf: gpd.GeoDataFrame,
    irem_raster_dir: Union[str, Path],
    landtype_raster: Union[str, Path],
    *,
    label: str,
    uniqueID: str = "uniqueID",
    filename_prefix: str = "irem_",
    nodata_to: float = 0.0,
    auto_align_landtype: bool = False,
    resampling: Resampling = Resampling.nearest,
) -> gpd.GeoDataFrame:
    """
    Join landtype exposure results onto a GeoDataFrame by uniqueID.
    """
    if uniqueID not in gdf.columns:
        raise ValueError(f"'{uniqueID}' not found in gdf.")

    ex = compute_landtype_exposure(
        irem_raster_dir,
        landtype_raster,
        label=label,
        filename_prefix=filename_prefix,
        nodata_to=nodata_to,
        auto_align_landtype=auto_align_landtype,
        resampling=resampling,
    )

    out = gdf.copy()
    out["_join_id"] = out[uniqueID].astype(str)
    ex["_join_id"] = ex["uniqueID"].astype(str)

    out = out.merge(ex.drop(columns=["uniqueID", "raster_path"]), on="_join_id", how="left")
    out = out.drop(columns=["_join_id"])
    return out


# ---------------------------------------------------------------------
# 4) IREM rasters -> polygons
# ---------------------------------------------------------------------

def irem_rasters_to_polygons(
    irem_raster_dir: Union[str, Path],
    *,
    uniqueID: str = "uniqueID",
    filename_prefix: str = "irem_",
    nodata_to: float = 0.0,
    percentile: float = 50.0,
    simplify: bool = False,
    simplify_tolerance: Optional[float] = None,  # None -> ~1 pixel
    connectivity: int = 8,  # 4 or 8
    output_path: Optional[Union[str, Path]] = None,
    driver: str = "GPKG",
) -> gpd.GeoDataFrame:
    """
    Convert a folder of IREM rasters into one polygon per individual using a percentile threshold.

    For each raster:
      1) read values (nodata -> nodata_to)
      2) compute threshold from the percentile of UNIQUE non-zero values
      3) mask pixels >= threshold
      4) polygonize the mask
      5) dissolve into one polygon per person
    """
    paths = _list_rasters(irem_raster_dir, filename_prefix=filename_prefix)

    records: list[dict] = []
    for p in paths:
        uid = _parse_id_from_filename(p, filename_prefix=filename_prefix)

        with rasterio.open(p) as src:
            arr = src.read(1).astype("float32", copy=False)
            nodata = src.nodata
            if nodata is not None:
                arr = np.where(arr == nodata, float(nodata_to), arr)
            arr = np.nan_to_num(arr, nan=float(nodata_to))

            flat = arr.ravel()
            nonzero = flat[flat != 0]
            if nonzero.size == 0:
                continue

            unique_vals = np.unique(nonzero)
            thr = float(np.percentile(unique_vals, float(percentile)))

            mask_arr = arr >= thr

            geom_list = []
            for geom_mapping, value in shapes(
                mask_arr.astype(np.uint8),
                mask=mask_arr,
                transform=src.transform,
                connectivity=int(connectivity),
            ):
                if value != 1:
                    continue
                geom_list.append(shape(geom_mapping))

            if not geom_list:
                continue

            dissolved = unary_union(geom_list)

            if simplify:
                tol = float(abs(src.transform.a)) if simplify_tolerance is None else float(simplify_tolerance)
                dissolved = dissolved.simplify(tol, preserve_topology=True)

            records.append({uniqueID: str(uid), "geometry": dissolved})

    if not records:
        return gpd.GeoDataFrame({uniqueID: []}, geometry=[], crs=None)

    with rasterio.open(paths[0]) as src0:
        out_crs = src0.crs

    gdf = gpd.GeoDataFrame(records, crs=out_crs)
    gdf = gdf.loc[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(output_path, driver=driver)

    return gdf


# ---------------------------------------------------------------------
# 5) Jenks tool: optimum distance from a numeric series (natural breaks)
# ---------------------------------------------------------------------

def jenks_breaks(values: list[float], num_classes: int) -> list[float]:
    """
    Compute Jenks natural breaks for `values` into `num_classes` classes.

    Returns a list of breakpoints (length num_classes + 1). The first value is 0.0
    to keep indexing simple and mirror common Jenks implementations.
    """
    data = sorted(float(v) for v in values)
    n = len(data)
    if n == 0:
        raise ValueError("values is empty.")
    if num_classes < 2:
        raise ValueError("num_classes must be >= 2.")
    if num_classes > n:
        raise ValueError("num_classes cannot exceed number of values.")

    mat1 = [[0] * (num_classes + 1) for _ in range(n + 1)]
    mat2 = [[0.0] * (num_classes + 1) for _ in range(n + 1)]

    for j in range(1, num_classes + 1):
        mat1[1][j] = 1
        mat2[1][j] = 0.0
        for i in range(2, n + 1):
            mat2[i][j] = float("inf")

    v = 0.0
    for l in range(2, n + 1):
        s1 = 0.0
        s2 = 0.0
        w = 0.0

        for m in range(1, l + 1):
            i3 = l - m + 1
            val = data[i3 - 1]
            s2 += val * val
            s1 += val
            w += 1.0
            v = s2 - (s1 * s1) / w
            i4 = i3 - 1

            if i4 != 0:
                for j in range(2, num_classes + 1):
                    if mat2[l][j] >= (v + mat2[i4][j - 1]):
                        mat1[l][j] = i3
                        mat2[l][j] = v + mat2[i4][j - 1]

        mat1[l][1] = 1
        mat2[l][1] = v

    k = n
    kclass = [0.0] * (num_classes + 1)
    kclass[num_classes] = data[-1]

    count = num_classes
    while count >= 2:
        idx = int(mat1[k][count] - 2)
        kclass[count - 1] = data[idx]
        k = int(mat1[k][count] - 1)
        count -= 1

    return kclass


def jenks_gvf(values: list[float], num_classes: int) -> float:
    """
    Goodness of Variance Fit (GVF) for Jenks breaks.
    Higher is better; 1.0 means perfect classification.
    """
    data = sorted(float(v) for v in values)
    n = len(data)
    if n == 0:
        raise ValueError("values is empty.")
    if num_classes < 2:
        raise ValueError("num_classes must be >= 2.")
    if num_classes > n:
        raise ValueError("num_classes cannot exceed number of values.")

    breaks = jenks_breaks(data, num_classes)
    mean_all = float(sum(data) / n)

    sdam = sum((x - mean_all) ** 2 for x in data)

    sdcm = 0.0
    for i in range(num_classes):
        lo = breaks[i]
        hi = breaks[i + 1]

        if lo == 0.0:
            start = 0
        else:
            start = data.index(lo) + 1
        end = data.index(hi)

        cls = data[start : end + 1]
        if not cls:
            continue
        mean_c = float(sum(cls) / len(cls))
        sdcm += sum((x - mean_c) ** 2 for x in cls)

    return (sdam - sdcm) / sdam if sdam != 0 else 1.0


def optimum_distance_jenks(
    values: Union[pd.Series, np.ndarray, list[float]],
    *,
    gvf_target: float = 0.98,
    percentile: float = 80.0,
    apply_threshold: bool = False,
    threshold: Optional[float] = None,
    min_classes: int = 2,
    max_classes: Optional[int] = None,
) -> dict:
    """
    Estimate an "optimum distance" threshold from a numeric vector using Jenks optimization.

    Algorithm:
      1) Optionally filter values < threshold (if apply_threshold=True)
      2) Increase number of classes until GVF >= gvf_target
      3) Compute Jenks breaks
      4) Compute p = percentile(values)
      5) Return the first break >= p

    Returns a dict with:
      - optimum_distance
      - num_classes
      - gvf
      - percentile_value
      - breaks
      - n_used

    Notes
    -----
    - Values are treated as unitless numbers. If these are distances, make sure your input
      distances are already in meters.
    """
    arr = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        raise ValueError("No finite numeric values provided.")

    if apply_threshold:
        if threshold is None:
            raise ValueError("threshold must be provided when apply_threshold=True.")
        arr = arr[arr < float(threshold)]
        if arr.size == 0:
            raise ValueError("All values were removed by threshold filtering.")

    data = [float(x) for x in arr.tolist()]
    n = len(data)

    if max_classes is None:
        max_classes = min(25, n)  # practical cap
    max_classes = int(max_classes)

    if n < 2:
        raise ValueError("Need at least 2 values for Jenks classification.")

    # GVF loop
    gvf = 0.0
    k = max(int(min_classes), 2)

    while gvf < float(gvf_target):
        k += 1
        if k > max_classes:
            # stop at cap; return best we got
            k = max_classes
            gvf = jenks_gvf(data, k)
            break
        gvf = jenks_gvf(data, k)

    breaks = jenks_breaks(data, k)

    p_val = float(np.percentile(np.asarray(data, dtype=float), float(percentile)))

    # pick first break >= p_val (skip the leading 0.0 placeholder)
    opt = None
    for b in breaks[1:]:
        if float(b) >= p_val:
            opt = float(b)
            break
    if opt is None:
        opt = float(breaks[-1])

    return {
        "optimum_distance": opt,
        "num_classes": int(k),
        "gvf": float(gvf),
        "percentile_value": float(p_val),
        "breaks": [float(x) for x in breaks],
        "n_used": int(n),
    }