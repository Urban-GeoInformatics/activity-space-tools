"""
ActivitySpace Tools — Example End-to-End Workflow
-------------------------------------------------

This script demonstrates how to use the main functions of the
`activityspace` Python library.

The workflow follows a typical research pipeline:

1. Load spatial data (homes, activity points, routes)
2. Compute distance-to-home metrics (Spider model)
3. Generate activity space polygons (Home Range model)
4. Generate raster exposure surfaces (IREM model)
5. Summarize exposure values
6. Calculate geometric metrics of activity spaces
7. Convert IREM rasters to polygons

The script assumes that the test data are stored in:

    test_data/
        eep.shp      → activity / destination points
        Home.shp     → home locations
        routes.shp   → routes between homes and destinations

All results will be written to:

    test_output/
"""

from pathlib import Path
import geopandas as gpd

# Import functions from the activityspace library
from activityspace.spider import add_distance_to_home
from activityspace.home_range import model_home_range
from activityspace.irem import run_irem, IREMParams
from activityspace.analytics import (
    summarize_rasters,
    exposure_summary,
    as_geometry_calculator,
    irem_rasters_to_polygons,
)

# ------------------------------------------------
# PATH CONFIGURATION
# ------------------------------------------------

# Folder containing the example datasets
DATA_DIR = Path("test_data")

# Folder where all outputs will be saved
OUT_DIR = Path("test_output")

# Folder where IREM rasters will be written
IREM_DIR = OUT_DIR / "irem_rasters"

# Input datasets
poi_path = DATA_DIR / "eep.shp"       # points of interest / activity locations
home_path = DATA_DIR / "Home.shp"     # home locations of individuals
routes_path = DATA_DIR / "routes.shp" # travel routes between home and destinations

# Create output folders if they do not exist
OUT_DIR.mkdir(exist_ok=True)
IREM_DIR.mkdir(exist_ok=True)

# ------------------------------------------------
# FIELD DEFINITIONS
# ------------------------------------------------
"""
These variables define the key attribute names used by the library.

uniqueID
    Identifies each person.

destinationID
    Identifies each destination / activity point.

poi_weight_col
    Weight or importance of each destination.

travel_mode_col
    Optional column describing travel mode.
"""

uniqueID = "uid"
destinationID = "DESTid"
poi_weight_col = "weight"
travel_mode_col = "travelMode"

# ------------------------------------------------
# LOAD DATA
# ------------------------------------------------

print("\nLoading test data...")

# Read shapefiles as GeoDataFrames
poi = gpd.read_file(poi_path)
home = gpd.read_file(home_path)
routes = gpd.read_file(routes_path)

print("POI rows:", len(poi))
print("Home rows:", len(home))
print("Routes rows:", len(routes))

# ------------------------------------------------
# TEST 1: SPIDER MODEL
# ------------------------------------------------
"""
The Spider model computes the distance between each activity
location and the individual's home.

The function adds a new column:

    dist_m  → distance to home in meters
"""

print("\nRunning spider distance calculation...")

spider_out = add_distance_to_home(
    poi=poi,
    home=home,
    uniqueID=uniqueID,
)

# Display summary statistics of distances
print("Distance stats:")
print(spider_out["dist_m"].describe())

# Save results for inspection
spider_out.to_file(OUT_DIR / "spider_result.gpkg")

# ------------------------------------------------
# TEST 2: HOME RANGE MODEL
# ------------------------------------------------
"""
The Home Range model constructs an activity space polygon
based on:

    • home locations
    • activity points

Each point contributes a buffer influence area which is merged
into a single activity space polygon for each person.
"""

print("\nRunning home range model...")

home_range = model_home_range(
    poi=poi,
    home=home,
    uniqueID=uniqueID,

    # influence radius around home
    home_effect_radius_m=500,

    # influence radius around activity points
    poi_effect_radius_m=100,
)

print("Home ranges created:", len(home_range))

home_range.to_file(OUT_DIR / "home_range_result.gpkg")

# ------------------------------------------------
# TEST 3: IREM MODEL
# ------------------------------------------------
"""
IREM (Individualized Residential Exposure Model) generates
continuous raster exposure surfaces representing how individuals
experience the environment based on:

    • home locations
    • activity points
    • routes between them

The output is a raster surface for each individual.
"""

print("\nRunning IREM model...")

# Define model parameters
params = IREMParams(
    home_effect_radius_m=500,
    poi_effect_radius_m=100,
    route_effect_radius_m=10,

    # sampling density along routes
    route_point_interval_m=10,

    # boundary sampling
    boundary_point_interval_m=30,
    boundary_point_weight=0.05,

    # raster resolution
    cell_size_m=10,
)

# Run the model
rasters = run_irem(
    home=home,
    poi=poi,
    routes=routes,

    out_dir=IREM_DIR,

    uniqueID=uniqueID,
    destinationID=destinationID,

    travel_mode_col=travel_mode_col,
    poi_weight_col=poi_weight_col,

    params=params,
)

print("IREM rasters created:", len(rasters))

# ------------------------------------------------
# TEST 4: RASTER SUMMARY
# ------------------------------------------------
"""
Summarize statistics of all IREM rasters.

Output includes metrics such as:

    mean exposure
    total exposure
"""

print("\nSummarizing rasters...")

summary = summarize_rasters(
    raster_dir=IREM_DIR,
    filename_prefix="irem_",
)

print(summary.head())

summary.to_csv(OUT_DIR / "irem_summary.csv", index=False)

# ------------------------------------------------
# TEST 5: EXPOSURE SUMMARY
# ------------------------------------------------
"""
Combine raster exposure results with activity space polygons.

This attaches exposure metrics to each individual's
activity space geometry.
"""

print("\nComputing exposure summary...")

exposure = exposure_summary(
    gdf=home_range,
    raster_dir=IREM_DIR,
    uniqueID=uniqueID,
)

exposure.to_file(OUT_DIR / "exposure_summary.gpkg")

# ------------------------------------------------
# TEST 6: GEOMETRY METRICS
# ------------------------------------------------
"""
Compute geometric properties of activity space polygons.

Metrics include:

    area
    perimeter
    elongation
    orientation
"""

print("\nComputing geometry metrics...")

geom = as_geometry_calculator(
    polygons=home_range,
    uniqueID=uniqueID,
)

geom.to_file(OUT_DIR / "geometry_metrics.gpkg")

# ------------------------------------------------
# TEST 7: IREM POLYGONS
# ------------------------------------------------
"""
Convert IREM raster exposure surfaces into polygons.

These polygons represent areas where exposure
exceeds a specified percentile threshold.
"""

print("\nConverting rasters to polygons...")

irem_polygons = irem_rasters_to_polygons(
    irem_raster_dir=IREM_DIR,
    uniqueID=uniqueID,
)

irem_polygons.to_file(OUT_DIR / "irem_polygons.gpkg")

# ------------------------------------------------
# DONE
# ------------------------------------------------

print("\nAll tests finished successfully.")
print("Outputs written to:", OUT_DIR)