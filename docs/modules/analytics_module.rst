
Analytics Module
================

The **analytics module** provides tools for analyzing outputs generated
by the ActivitySpace Tools workflow.

These functions are designed to work with:

- home range polygons
- IREM raster outputs
- optional environmental rasters
- numeric vectors (e.g., travel distances)

The tools support common post-processing tasks in mobility and exposure
analysis workflows.


Expected IREM Raster Structure
------------------------------

The raster directory must contain files named::

   irem_<uniqueID>.tif

Example::

   irem_409683.tif
   irem_425004.tif

The ``<uniqueID>`` component must correspond to the identifier used in
your vector datasets.


Raster Summary Tools
--------------------

summarize_rasters()
^^^^^^^^^^^^^^^^^^^

Compute exposure summaries for each raster in an IREM output directory.

For each raster, the function:

1. Reads the raster values
2. Replaces nodata values (default: 0)
3. Computes mean exposure
4. Computes total exposure

Example:

.. code-block:: python

   from activityspace.analytics import summarize_rasters

   df = summarize_rasters(
       raster_dir="outputs/irem_rasters",
       filename_prefix="irem_"
   )

The result is a pandas DataFrame containing:

- ``uniqueID``
- ``raster_path``
- ``mean``
- ``total``


exposure_summary()
^^^^^^^^^^^^^^^^^^

Attach raster exposure metrics to a GeoDataFrame.

Example:

.. code-block:: python

   import geopandas as gpd
   from activityspace.analytics import exposure_summary

   gdf = gpd.read_file("people.gpkg")

   gdf2 = exposure_summary(
       gdf=gdf,
       raster_dir="outputs/irem_rasters",
       uniqueID="uid",
   )

The returned GeoDataFrame contains additional exposure columns.


Geometry Metrics
----------------

as_geometry_calculator()
^^^^^^^^^^^^^^^^^^^^^^^^

Compute geometric properties of polygon datasets.

Internally, geometries are temporarily reprojected to an automatically
selected local projected CRS so that measurements are computed in meters.

Metrics added:

- ``area_m2`` – polygon area in square meters
- ``perim_m`` – polygon perimeter in meters
- ``elong`` – elongation ratio
- ``orient`` – orientation of the major axis (degrees)


Example:

.. code-block:: python

   import geopandas as gpd
   from activityspace.analytics import as_geometry_calculator

   hr = gpd.read_file("home_ranges.gpkg")

   hr_metrics = as_geometry_calculator(
       polygons=hr,
       uniqueID="uid"
   )


Landtype Exposure Tools
-----------------------

These functions combine IREM rasters with an environmental raster
(e.g., green space mask, NDVI, water, or noise).

Exposure is calculated as::

   IREM * LANDTYPE

Two metrics are produced:

- total exposure
- average exposure


compute_landtype_exposure()
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Return exposure statistics in a table.

Example:

.. code-block:: python

   from activityspace.analytics import compute_landtype_exposure

   df = compute_landtype_exposure(
       irem_raster_dir="outputs/irem_rasters",
       landtype_raster="rasters/green_mask.tif",
       label="green"
   )


attach_landtype_exposure()
^^^^^^^^^^^^^^^^^^^^^^^^^^

Attach exposure metrics to a GeoDataFrame.

Example:

.. code-block:: python

   from activityspace.analytics import attach_landtype_exposure

   gdf2 = attach_landtype_exposure(
       gdf=gdf,
       irem_raster_dir="outputs/irem_rasters",
       landtype_raster="rasters/green_mask.tif",
       label="green",
       uniqueID="uid"
   )


IREM Raster to Polygon Conversion
---------------------------------

irem_rasters_to_polygons()
^^^^^^^^^^^^^^^^^^^^^^^^^^

Convert IREM rasters into polygons using percentile thresholding.

Algorithm:

1. Read raster values
2. Compute percentile threshold
3. Mask pixels above the threshold
4. Polygonize the mask
5. Dissolve into one polygon per individual

Example:

.. code-block:: python

   from activityspace.analytics import irem_rasters_to_polygons

   polys = irem_rasters_to_polygons(
       irem_raster_dir="outputs/irem_rasters",
       uniqueID="uid"
   )


Jenks Threshold Tool
--------------------

optimum_distance_jenks()
^^^^^^^^^^^^^^^^^^^^^^^^

Estimate an empirical threshold from a numeric vector using
Jenks natural breaks.

Example:

.. code-block:: python

   from activityspace.analytics import optimum_distance_jenks

   values = poi["dist_m"].dropna()

   result = optimum_distance_jenks(
       values,
       gvf_target=0.98,
       percentile=80
   )


Typical Workflow
----------------

A common workflow using these tools is:

1. Run ``run_irem()`` to generate exposure rasters.
2. Summarize rasters using ``summarize_rasters()``.
3. Attach exposure metrics using ``exposure_summary()``.
4. Compute geometry metrics for activity space polygons.
5. Convert rasters to polygons if needed.
6. Optionally compute landtype exposure.
7. Derive empirical thresholds using Jenks.


Notes
-----

The analytics module is designed for reproducible research workflows
in activity space modeling and environmental exposure analysis.

These tools are particularly useful for datasets describing everyday
mobility and participatory mapping data, including Public Participation
GIS (PPGIS) studies.
