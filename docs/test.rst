ActivitySpace Tools — Example Dataset and Workflow
=================================================

This section describes the example dataset and the complete workflow
included with the ``activityspace`` package.

The package provides:

- ``example_usage.py``: a ready-to-run script demonstrating the full workflow
- ``test_data/``: a small sample dataset for testing and learning

The example is designed to run out-of-the-box and demonstrates how to
move from raw spatial data to activity spaces, exposure estimates,
and summary metrics.

Quick start
-----------

After installing the package, you can run the full example workflow
using the included script and sample data.

1. Open a terminal and navigate to the package directory.

2. Run the example script:

::

    python example_usage.py

3. After execution, results will be written to:

::

    test_output/

During execution, the script prints progress messages and summary
information to the terminal.

Test Data
---------

The dataset is derived from anonymized Public Participation GIS (PPGIS)
data originally collected in Oulu, Finland. To protect privacy, the
data have been simplified and reduced to a minimal example suitable
for testing.

The dataset represents mobility information for two individuals
and includes a total of eight activity markings.

It is intentionally small so that the full workflow can be executed
quickly.

Data files
----------

The example uses the following files inside ``test_data/``:

::

    test_data/
        eep.shp
        Home.shp
        routes.shp

Home.shp
^^^^^^^^

Point dataset representing the home locations of individuals.

Attributes include::

   uid
   geometry

Each individual has one home location.

eep.shp
^^^^^^^

Point dataset representing Everyday Errand Points (EEPs) or
destinations visited by individuals.

These points originate from PPGIS survey responses where participants
marked locations they frequently visit.

Attributes include::

   uid
   DESTid
   weight
   travelMode
   geometry

The example dataset includes eight activity points in total.

routes.shp
^^^^^^^^^^

Line dataset representing precomputed shortest routes between each
individual's home location and their activity points.

Routes were calculated beforehand using a routing algorithm on a road
network.

Attributes include::

   uid
   DESTid
   geometry

Each route connects a home location with a corresponding activity point.

Example workflow
----------------

The file ``example_usage.py`` demonstrates a complete workflow using
ActivitySpace Tools.

The workflow follows a typical research pipeline:

1. Load spatial data
2. Compute distance-to-home metrics
3. Generate activity space polygons
4. Generate raster exposure surfaces
5. Summarize raster exposure
6. Compute exposure and geometry metrics
7. Convert raster exposure surfaces to polygons

Path configuration
------------------

The script first defines the input and output paths:

.. code-block:: python

    from pathlib import Path
    import geopandas as gpd

    from activityspace.spider import add_distance_to_home
    from activityspace.home_range import model_home_range
    from activityspace.irem import run_irem, IREMParams
    from activityspace.analytics import (
        summarize_rasters,
        exposure_summary,
        as_geometry_calculator,
        irem_rasters_to_polygons,
    )

    DATA_DIR = Path("test_data")
    OUT_DIR = Path("test_output")
    IREM_DIR = OUT_DIR / "irem_rasters"

    poi_path = DATA_DIR / "eep.shp"
    home_path = DATA_DIR / "Home.shp"
    routes_path = DATA_DIR / "routes.shp"

    OUT_DIR.mkdir(exist_ok=True)
    IREM_DIR.mkdir(exist_ok=True)

The script also defines the attribute names used throughout the workflow:

.. code-block:: python

    uniqueID = "uid"
    destinationID = "DESTid"
    poi_weight_col = "weight"
    travel_mode_col = "travelMode"

Step 1: Load spatial datasets
-----------------------------

The workflow begins by loading the example data as GeoDataFrames:

.. code-block:: python

    print("\nLoading test data...")

    poi = gpd.read_file(poi_path)
    home = gpd.read_file(home_path)
    routes = gpd.read_file(routes_path)

    print("POI rows:", len(poi))
    print("Home rows:", len(home))
    print("Routes rows:", len(routes))

These datasets are then used as inputs in the following steps.

Step 2: Compute distance-to-home metrics
----------------------------------------

The Spider model calculates the distance between each activity
location and the individual's home.

.. code-block:: python

    print("\nRunning spider distance calculation...")

    spider_out = add_distance_to_home(
        poi=poi,
        home=home,
        uniqueID=uniqueID,
    )

    print("Distance stats:")
    print(spider_out["dist_m"].describe())

    spider_out.to_file(OUT_DIR / "spider_result.gpkg")

This step adds a new column:

- ``dist_m``: distance from each activity point to home in meters

Output:

::

    test_output/spider_result.gpkg

Step 3: Generate activity space polygons
----------------------------------------

The Home Range model creates an activity space polygon for each
individual using home locations and activity points.

.. code-block:: python

    print("\nRunning home range model...")

    home_range = model_home_range(
        poi=poi,
        home=home,
        uniqueID=uniqueID,
        home_effect_radius_m=500,
        poi_effect_radius_m=100,
    )

    print("Home ranges created:", len(home_range))

    home_range.to_file(OUT_DIR / "home_range_result.gpkg")

Conceptually, this step buffers home and activity locations and merges
their areas of influence into a single polygon per individual.

Output:

::

    test_output/home_range_result.gpkg

Step 4: Generate raster exposure surfaces
-----------------------------------------

The IREM (Individualized Residential Exposure Model) produces continuous
raster exposure surfaces based on home locations, activity locations,
and travel routes.

First, model parameters are defined:

.. code-block:: python

    params = IREMParams(
        home_effect_radius_m=500,
        poi_effect_radius_m=100,
        route_effect_radius_m=10,
        route_point_interval_m=10,
        boundary_point_interval_m=30,
        boundary_point_weight=0.05,
        cell_size_m=10,
    )

Then the model is run:

.. code-block:: python

    print("\nRunning IREM model...")

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

Output:

- one raster per individual
- rasters written to:

::

    test_output/irem_rasters/

Step 5: Summarize raster exposure
---------------------------------

Raster outputs can be summarized into tabular metrics such as mean
and total exposure.

.. code-block:: python

    print("\nSummarizing rasters...")

    summary = summarize_rasters(
        raster_dir=IREM_DIR,
        filename_prefix="irem_",
    )

    print(summary.head())

    summary.to_csv(OUT_DIR / "irem_summary.csv", index=False)

Output:

::

    test_output/irem_summary.csv

Step 6: Compute exposure and geometry metrics
---------------------------------------------

Exposure values can be linked to activity space polygons:

.. code-block:: python

    print("\nComputing exposure summary...")

    exposure = exposure_summary(
        gdf=home_range,
        raster_dir=IREM_DIR,
        uniqueID=uniqueID,
    )

    exposure.to_file(OUT_DIR / "exposure_summary.gpkg")

Geometric properties of the activity space polygons can also be computed:

.. code-block:: python

    print("\nComputing geometry metrics...")

    geom = as_geometry_calculator(
        polygons=home_range,
        uniqueID=uniqueID,
    )

    geom.to_file(OUT_DIR / "geometry_metrics.gpkg")

These metrics may include:

- area
- perimeter
- elongation
- orientation

Outputs:

::

    test_output/exposure_summary.gpkg
    test_output/geometry_metrics.gpkg

Step 7: Convert exposure rasters to polygons
--------------------------------------------

IREM raster exposure surfaces can be converted into polygons
representing areas above a threshold.

.. code-block:: python

    print("\nConverting rasters to polygons...")

    irem_polygons = irem_rasters_to_polygons(
        irem_raster_dir=IREM_DIR,
        uniqueID=uniqueID,
    )

    irem_polygons.to_file(OUT_DIR / "irem_polygons.gpkg")

Output:

::

    test_output/irem_polygons.gpkg

These polygons represent areas of relatively higher exposure.

Complete example script
-----------------------

For convenience, the package includes the full example script
``example_usage.py``. The complete workflow is shown below.

.. code-block:: python

    from pathlib import Path
    import geopandas as gpd

    from activityspace.spider import add_distance_to_home
    from activityspace.home_range import model_home_range
    from activityspace.irem import run_irem, IREMParams
    from activityspace.analytics import (
        summarize_rasters,
        exposure_summary,
        as_geometry_calculator,
        irem_rasters_to_polygons,
    )

    DATA_DIR = Path("test_data")
    OUT_DIR = Path("test_output")
    IREM_DIR = OUT_DIR / "irem_rasters"

    poi_path = DATA_DIR / "eep.shp"
    home_path = DATA_DIR / "Home.shp"
    routes_path = DATA_DIR / "routes.shp"

    OUT_DIR.mkdir(exist_ok=True)
    IREM_DIR.mkdir(exist_ok=True)

    uniqueID = "uid"
    destinationID = "DESTid"
    poi_weight_col = "weight"
    travel_mode_col = "travelMode"

    print("\nLoading test data...")

    poi = gpd.read_file(poi_path)
    home = gpd.read_file(home_path)
    routes = gpd.read_file(routes_path)

    print("POI rows:", len(poi))
    print("Home rows:", len(home))
    print("Routes rows:", len(routes))

    print("\nRunning spider distance calculation...")

    spider_out = add_distance_to_home(
        poi=poi,
        home=home,
        uniqueID=uniqueID,
    )

    print("Distance stats:")
    print(spider_out["dist_m"].describe())

    spider_out.to_file(OUT_DIR / "spider_result.gpkg")

    print("\nRunning home range model...")

    home_range = model_home_range(
        poi=poi,
        home=home,
        uniqueID=uniqueID,
        home_effect_radius_m=500,
        poi_effect_radius_m=100,
    )

    print("Home ranges created:", len(home_range))

    home_range.to_file(OUT_DIR / "home_range_result.gpkg")

    print("\nRunning IREM model...")

    params = IREMParams(
        home_effect_radius_m=500,
        poi_effect_radius_m=100,
        route_effect_radius_m=10,
        route_point_interval_m=10,
        boundary_point_interval_m=30,
        boundary_point_weight=0.05,
        cell_size_m=10,
    )

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

    print("\nSummarizing rasters...")

    summary = summarize_rasters(
        raster_dir=IREM_DIR,
        filename_prefix="irem_",
    )

    print(summary.head())

    summary.to_csv(OUT_DIR / "irem_summary.csv", index=False)

    print("\nComputing exposure summary...")

    exposure = exposure_summary(
        gdf=home_range,
        raster_dir=IREM_DIR,
        uniqueID=uniqueID,
    )

    exposure.to_file(OUT_DIR / "exposure_summary.gpkg")

    print("\nComputing geometry metrics...")

    geom = as_geometry_calculator(
        polygons=home_range,
        uniqueID=uniqueID,
    )

    geom.to_file(OUT_DIR / "geometry_metrics.gpkg")

    print("\nConverting rasters to polygons...")

    irem_polygons = irem_rasters_to_polygons(
        irem_raster_dir=IREM_DIR,
        uniqueID=uniqueID,
    )

    irem_polygons.to_file(OUT_DIR / "irem_polygons.gpkg")

    print("\nAll tests finished successfully.")
    print("Outputs written to:", OUT_DIR)

Outputs
-------

Running the example script produces outputs in:

::

    test_output/

These include:

- ``spider_result.gpkg``: distance-to-home results
- ``home_range_result.gpkg``: activity space polygons
- ``irem_rasters/``: exposure rasters
- ``irem_summary.csv``: raster summary statistics
- ``exposure_summary.gpkg``: exposure linked to activity spaces
- ``geometry_metrics.gpkg``: geometric metrics
- ``irem_polygons.gpkg``: polygonized exposure outputs

Purpose
-------

These files are intended only for:

- testing library functionality
- demonstrating example workflows
- providing reproducible examples

The dataset is simplified and should not be interpreted as a full
research dataset.