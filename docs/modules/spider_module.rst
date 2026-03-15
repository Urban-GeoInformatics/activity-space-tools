
Spider Model
============

The **Spider model** computes the Euclidean distance (in meters) between
activity locations and corresponding home locations.

This module is useful for mobility studies where the spatial relationship
between daily destinations and home location is required. The function
matches each activity point with its corresponding home location and
computes the distance between them.

Distances are always returned in **meters**, regardless of the original CRS.


Function
--------

::

   add_distance_to_home()


Example
-------

.. code-block:: python

   import geopandas as gpd
   from activityspace.spider import add_distance_to_home

   poi = gpd.read_file("eep.shp")
   home = gpd.read_file("Home.shp")

   result = add_distance_to_home(
       poi=poi,
       home=home,
       uniqueID="uid"
   )

   print(result.head())

The output GeoDataFrame will contain a new column::

   dist_m

which stores the distance between the activity location and the home
location in meters.


Parameters
----------

::

   add_distance_to_home(
       poi,
       home,
       *,
       uniqueID,
       home_key=None,
       distance_col="dist_m",
       metric_crs="auto",
       keep_original_crs=True,
       duplicate_home_policy="error",
       missing_value=np.nan,
   )

Parameter description
^^^^^^^^^^^^^^^^^^^^^

**poi**

GeoDataFrame containing activity locations (points).

**home**

GeoDataFrame containing home locations (points).

**uniqueID**

Column used to match activity locations with home locations.

**home_key**

Optional column name in the home dataset if it differs from the POI key.

**distance_col**

Name of the output distance column.

**metric_crs**

Projected CRS used for distance calculation.
By default, a suitable local UTM CRS is automatically selected.

**keep_original_crs**

If True, the output geometry is returned in the original POI CRS.

**duplicate_home_policy**

Strategy for handling duplicate home identifiers:

- "error" – raise an error (default)
- "first" – keep the first occurrence
- "mean" – average coordinates for duplicate entries

**missing_value**

Value assigned when no matching home location is found.


CRS Handling
------------

Distances must be computed in a projected coordinate system.

The function automatically:

- detects geographic CRS
- selects a suitable projected CRS
- performs calculations in meters
- optionally returns results in the original CRS


Notes
-----

The Spider model is particularly useful for datasets where individuals
report locations of daily activities relative to their home location.
This includes mobility datasets derived from:

- travel surveys
- GPS tracking
- participatory mapping
- Public Participation GIS (PPGIS) studies

For methodological background and research applications of activity
space analysis, please refer to the associated scientific publications.
