ActivitySpace Tools
===================

ActivitySpace Tools is a Python library for modeling individual activity spaces and
analyzing human mobility patterns using geospatial data.

The library provides tools for:

- computing distance-to-home metrics
- generating activity space geometries
- modeling exposure surfaces
- analyzing the spatial properties of activity spaces

The package is intended for research and applied work in:

- human mobility
- urban analytics
- environmental exposure
- GIScience
- transport geography
- spatial behavior analysis

Scientific Background
---------------------

The methods implemented in ActivitySpace Tools originate from peer-reviewed research
on human activity spaces, environmental exposure, and mobility behavior.

The package implements computational tools based on the following research themes:

- activity space conceptualization
- environmental exposure through activity space modeling
- the Individualized Residential Exposure Model (IREM)

Main Modules
------------

Spider model
^^^^^^^^^^^^

Computes distance-to-home metrics for activity locations.

Home Range model
^^^^^^^^^^^^^^^^

Generates activity space polygons based on home locations and visited destinations.

IREM model
^^^^^^^^^^

The Individualized Residential Exposure Model (IREM) produces raster exposure
surfaces representing how individuals experience the spatial environment during
daily mobility.

Analytics tools
^^^^^^^^^^^^^^^

Additional functions for analyzing activity spaces and exposure surfaces, including:

- raster exposure summaries
- geometry metrics
- raster-to-polygon conversion
- exposure statistics

Installation
------------

Install from PyPI:

.. code-block:: bash

   pip install activity-space-tools

Or install locally for development:

.. code-block:: bash

   pip install -e .

Basic Example
-------------

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

Typical Workflow
----------------

A typical workflow using ActivitySpace Tools includes:

1. computing distance-to-home metrics
2. generating activity space polygons
3. modeling exposure surfaces with IREM
4. summarizing exposure statistics
5. analyzing geometry of activity spaces
6. converting exposure rasters to polygons

Citation
--------

If you use this library in academic work, please cite the associated scientific
publications and the software itself.

Suggested software citation:

.. code-block:: text

   Hasanzadeh, K. ActivitySpace Tools: Python tools for modeling
   individual activity spaces and environmental exposure.

License
-------

This project is licensed under the MIT License.

Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: Documentation

   installation
   usage
   modules
