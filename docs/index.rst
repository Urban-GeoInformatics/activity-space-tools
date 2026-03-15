# ActivitySpace Tools

ActivitySpace Tools is a Python library for modeling **individual activity spaces**
and analyzing human mobility patterns using geospatial data.

The library provides tools for computing distance-based mobility metrics,
generating activity space geometries, modeling exposure surfaces, and
analyzing spatial properties of activity spaces.

The package was developed primarily for research applications in:

* Human mobility
* Urban analytics
* Environmental exposure
* GIScience
* Transport geography
* Spatial behavior analysis

The library is particularly well suited for analyzing mobility data
collected through participatory mapping and Public Participation GIS
(PPGIS) surveys, where individuals report locations of daily activities
and experiences in geographic space.

## Scientific Background

The methods implemented in **ActivitySpace Tools** originate from
peer-reviewed research on human activity spaces, environmental exposure,
and mobility behavior.

Activity space conceptualization
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Hasanzadeh, K., Laatikainen, T., & Kyttä, M.

*Where is the neighborhood? A spatiotemporal perspective on human activity spaces.*

This work discusses how activity spaces can be conceptualized beyond
static residential neighborhoods and introduces approaches for
representing individualized spatial behavior using mobility data.

Environmental exposure and activity spaces
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Hasanzadeh, K., et al.

*Capturing environmental exposure through activity space modeling.*

This research demonstrates how daily mobility patterns influence
the environmental conditions individuals are exposed to.

Individualized Residential Exposure Model (IREM)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Hasanzadeh, K.

*Individualized Residential Exposure Model (IREM).*

IREM integrates

* home locations
* activity locations
* travel routes

to generate continuous spatial exposure surfaces that represent how
individuals experience environments through their daily mobility.

## Features

ActivitySpace Tools currently provides four main modules.

Spider model
^^^^^^^^^^^^

Computes **distance-to-home metrics** for activity locations.

Useful for studying:

* travel distances
* mobility behavior
* spatial reach of daily activities

Home Range model
^^^^^^^^^^^^^^^^

Generates **activity space polygons** based on home locations and
visited destinations.

These polygons approximate the spatial extent of an individual's
daily activity area.

IREM model
^^^^^^^^^^

The **Individualized Residential Exposure Model (IREM)** produces
raster exposure surfaces representing how individuals experience
the spatial environment during daily mobility.

Inputs include:

* home locations
* activity points
* travel routes

Analytics tools
^^^^^^^^^^^^^^^

Additional functions for analyzing activity spaces and exposure surfaces:

* raster exposure summaries
* geometry metrics
* raster-to-polygon conversion
* exposure statistics

## Basic Example

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

## Data Requirements

Typical workflows require three spatial datasets.

Home locations
^^^^^^^^^^^^^^

Point dataset representing individuals' home locations.

Example fields::

   uid
   geometry

Activity locations (POIs)
^^^^^^^^^^^^^^^^^^^^^^^^^

Point dataset representing visited destinations.

Example fields::

   uid
   DESTid
   weight
   travelMode
   geometry

Routes
^^^^^^

Line dataset representing travel paths between home and destinations.

Example fields::

   uid
   DESTid
   geometry

## Example Workflow

A typical workflow using ActivitySpace Tools:

1. Compute distance-to-home metrics (Spider model)
2. Generate activity space polygons (Home Range model)
3. Model exposure surfaces (IREM model)
4. Summarize exposure statistics
5. Analyze geometry of activity spaces
6. Convert exposure rasters to polygons

Conceptually the workflow looks like::

   Home points
   ↓
   Activity points
   ↓
   Routes
   ↓
   IREM exposure surfaces
   ↓
   Activity space analysis

## Dependencies

The library depends on commonly used geospatial Python libraries:

* geopandas
* pandas
* numpy
* shapely
* scipy
* rasterio
* pyproj

## Author

Kamyar Hasanzadeh
University of Helsinki

## Citation

If you use this library in academic work, please cite both the
software and the associated scientific publications.

Suggested citation::

Kamyar. (2026). Urban-GeoInformatics/activity-space-tools: 0.1.0 (0.1.0). Zenodo. https://doi.org/10.5281/zenodo.19036426

## License

MIT License

Copyright (c) 2026 Kamyar Hasanzadeh


.. toctree::
   :maxdepth: 2
   :caption: Documentation

   installation
   usage
   test


.. toctree::
   :maxdepth: 2
   :caption: Modules

   modules/spider_module
   modules/home_range_module
   modules/irem_module
   modules/analytics_module