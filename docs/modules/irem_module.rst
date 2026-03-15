
IREM Model
==========

The **IREM model** (Individualized Residential Exposure Model) generates
one raster exposure surface per individual and writes the results as
GeoTIFF files.

The model combines:

- home locations
- activity locations
- routes between home and destinations

to produce individualized exposure surfaces that can be used in
mobility and environmental exposure analysis.

The implementation is designed for reproducible research workflows and
supports restartable processing for longer runs.


Function
--------

::

   run_irem()


What the model does
-------------------

For each individual, the model:

1. Builds a person-specific boundary using home locations, activity
   locations, and routes
2. Generates weighted point inputs from home locations, activity points,
   route points, and boundary support points
3. Creates raster surfaces using inverse distance weighting (IDW)
4. Sums the resulting surfaces
5. Writes the final raster as a clipped GeoTIFF


Inputs
------

The function requires three GeoDataFrames.

**home**

Point dataset containing home locations.

Required:

- person identifier column
- Point geometry

**poi**

Point dataset containing activity locations or destinations.

Required:

- person identifier column
- destination identifier column
- POI weight column
- Point geometry

Optional:

- travel mode column

**routes**

Line dataset containing routes between home and destinations.

Required:

- destination identifier column
- LineString or MultiLineString geometry


Example
-------

.. code-block:: python

   import geopandas as gpd
   from activityspace.irem import run_irem, IREMParams

   home = gpd.read_file("Home.shp")
   poi = gpd.read_file("eep.shp")
   routes = gpd.read_file("routes.shp")

   params = IREMParams(
       home_effect_radius_m=500,
       poi_effect_radius_m=100,
       route_effect_radius_m=10,
       route_point_interval_m=10,
       boundary_point_interval_m=30,
       boundary_point_weight=0.05,
       cell_size_m=10,
   )

   written_files = run_irem(
       home=home,
       poi=poi,
       routes=routes,
       out_dir="outputs/irem_rasters",
       uniqueID="uid",
       destinationID="DESTid",
       travel_mode_col="travelMode",
       poi_weight_col="weight",
       params=params,
   )

   print(f"Wrote {len(written_files)} rasters.")


Output
------

The function writes one raster per individual using the naming pattern::

   irem_<uniqueID>.tif

The function returns a list of output file paths.

Rasters are written in a projected metric CRS chosen automatically from
the home locations, and each raster is clipped to the individual's
boundary geometry.


Parameters
----------

::

   run_irem(
       home,
       poi,
       routes,
       *,
       out_dir,
       uniqueID="uniqueID",
       destinationID="destinationID",
       travel_mode_col="travelMode",
       poi_weight_col="weight",
       max_poi_weight=30.0,
       params=IREMParams(),
       mode_map=None,
       default_mode="motorized",
       skip_existing=True,
       show_progress=True,
       continue_on_error=True,
   )

Important parameter notes
^^^^^^^^^^^^^^^^^^^^^^^^^

**out_dir**

Output folder where GeoTIFF files will be written.

**uniqueID**

Column identifying individuals in the home and POI layers.

**destinationID**

Column linking POIs to route geometries.

**travel_mode_col**

Optional travel mode column stored in the POI layer.

**poi_weight_col**

Column storing POI weights.

**max_poi_weight**

Maximum allowed POI weight. Values are clamped to the range
``[0, max_poi_weight]`` and normalized internally to ``[0, 1]``.

**params**

Optional ``IREMParams`` object used to tune model behavior.

**mode_map**

Optional dictionary for custom travel mode mapping.

**default_mode**

Fallback travel mode used when no valid mode is available.

**skip_existing**

If ``True``, existing output rasters are skipped.

**show_progress**

If ``True``, a progress bar is shown when ``tqdm`` is available.

**continue_on_error**

If ``True``, processing continues even if an individual fails.


Travel mode handling
--------------------

Travel mode is read from the POI layer and mapped internally to one of:

- ``walk``
- ``bike``
- ``motorized``

If no travel mode column is available, the default mode is used.

Route influence is scaled by travel mode:

- walk: ``1.0``
- bike: ``1 / 3.4``
- motorized: ``1 / 10``

A custom ``mode_map`` can be supplied if your data use different labels.


POI weight handling
-------------------

POI weights are processed as follows:

- values are converted to numeric form
- missing values are replaced with the mean of available values
- values below 0 are set to 0
- values above ``max_poi_weight`` are set to ``max_poi_weight``
- values are normalized internally to the range ``[0, 1]``

This makes the function easier to use with differently scaled survey data.


IREMParams
----------

Model settings can be adjusted through ``IREMParams``.

::

   IREMParams(
       home_effect_radius_m=500.0,
       poi_effect_radius_m=100.0,
       route_effect_radius_m=10.0,
       route_point_interval_m=5.0,
       boundary_point_interval_m=30.0,
       boundary_point_weight=0.05,
       cell_size_m=5.0,
       idw_power=2.0,
       idw_k=12,
       nodata=0.0,
       filename_prefix="irem_",
   )

These parameters control:

- home, POI, and route influence distances
- route densification
- boundary support sampling
- raster resolution
- IDW interpolation behavior
- output file naming


Restartable processing
----------------------

The IREM workflow supports restartable processing.

If ``skip_existing=True``, the function checks the output directory and
skips any individual whose raster already exists. This makes it easier
to resume long-running processing without repeating completed outputs.


Progress and failures
---------------------

When progress reporting is enabled, the function iterates over
individuals and reports the current identifier.

If an individual fails:

- the identifier and error message are printed
- processing continues if ``continue_on_error=True``

This behavior is helpful for larger batch runs.


Notes
-----

The IREM model is especially useful for data describing everyday
mobility and spatial exposure, including participatory mapping and
Public Participation GIS (PPGIS) datasets where individuals report
destinations and travel behavior.

For methodological background and research applications, please refer
to the associated scientific publications.
