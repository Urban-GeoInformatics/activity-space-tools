
Home Range Model
================

The **Home Range model** constructs an individualized activity space
boundary from home locations and activity points.

The model combines:

- an immediate home effect around home locations
- a local area-of-effect around activity locations
- optional filtering of distant activity points

This module is useful for activity-space research, behavioral geography,
mobility studies, and exposure analysis.


Conceptual Overview
-------------------

The Home Range model represents an individual's spatial footprint by
combining buffered home locations and buffered activity locations into
a single enclosing boundary.

The workflow is:

1. Validate the input datasets
2. Optionally compute distance-to-home and filter far activity points
3. Buffer home locations using ``home_effect_radius_m``
4. Buffer activity locations using ``poi_effect_radius_m``
5. Merge buffered geometries for each individual
6. Construct one convex hull boundary per individual


Function
--------

::

   model_home_range()


Example
-------

.. code-block:: python

   import geopandas as gpd
   from activityspace.home_range import model_home_range

   poi = gpd.read_file("eep.shp")
   home = gpd.read_file("Home.shp")

   home_ranges = model_home_range(
       poi=poi,
       home=home,
       uniqueID="uid",
       home_effect_radius_m=500,
       poi_effect_radius_m=100,
   )

   print(home_ranges.head())

The output is a GeoDataFrame containing one polygon per individual.


Parameters
----------

::

   model_home_range(
       poi,
       home,
       *,
       uniqueID="uniqueID",
       home_effect_radius_m=500.0,
       poi_effect_radius_m=100.0,
       filter_far_pois=False,
       max_poi_distance_m=None,
       keep_fields=None,
   )

Parameter notes
^^^^^^^^^^^^^^^

**poi**

GeoDataFrame containing activity locations as point geometries.

**home**

GeoDataFrame containing home locations as point geometries.

**uniqueID**

Column identifying individuals in both datasets.

**home_effect_radius_m**

Immediate home effect radius, in meters when using a projected metric CRS.

**poi_effect_radius_m**

Area-of-effect radius around activity locations, in meters when using a
projected metric CRS.

**filter_far_pois**

If ``True``, activity locations farther than ``max_poi_distance_m`` from
home are excluded before boundary construction.

**max_poi_distance_m**

Maximum allowed distance from home when filtering is enabled.

**keep_fields**

Optional list of fields copied from the home dataset into the output.


Output
------

The function returns a GeoDataFrame containing:

- one polygon per individual
- the identifier column
- any requested ``keep_fields``
- geometry representing the modeled home range

The output CRS matches the input home CRS.


Distance Filtering
------------------

When ``filter_far_pois=True``, distance-to-home is computed internally
before filtering.

This uses the Spider distance function and applies
``duplicate_home_policy="first"`` when duplicate home identifiers are
present. A warning is emitted to make this behavior explicit.

This keeps the workflow self-contained while preserving reproducibility.


CRS Requirements
----------------

Both input datasets must have a defined CRS.

Because the model uses geometric buffering, a projected CRS with metric
units is strongly recommended. Buffer distances are interpreted in the
units of the input CRS.

If your data are in a geographic CRS, reproject them before running the
model.


Example with Distance Filtering
-------------------------------

.. code-block:: python

   home_ranges = model_home_range(
       poi=poi,
       home=home,
       uniqueID="uid",
       home_effect_radius_m=500,
       poi_effect_radius_m=100,
       filter_far_pois=True,
       max_poi_distance_m=2000,
   )

This workflow:

- computes distance-to-home internally
- removes activity points beyond the specified threshold
- constructs individualized home range polygons


Notes
-----

The Home Range model is especially useful for datasets describing
everyday destinations and spatial behavior, including participatory
mapping and Public Participation GIS (PPGIS) data.

For methodological background and research applications, please refer
to the associated scientific publications.
