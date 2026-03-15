Test Data and Example Workflow
==============================

This section describes the small example dataset used to demonstrate
and validate the functionality of the **ActivitySpace Tools** library.

The dataset is derived from anonymized **Public Participation GIS (PPGIS)**
data originally collected in **Oulu, Finland**. To protect privacy, the
data have been simplified and reduced to a minimal example suitable
for testing.

The dataset represents mobility information for **two individuals**
and includes a total of **eight activity markings**.


Files
-----

Home.shp
^^^^^^^^

Point dataset representing the **home locations** of individuals.

Attributes include::

   uid
   geometry

Each individual has one home location.


eep.shp
^^^^^^^

Point dataset representing **Everyday Errand Points (EEPs)** or
destinations visited by individuals.

These points originate from PPGIS survey responses where participants
marked locations they frequently visit.

Attributes include::

   uid
   DESTid
   weight
   travelMode
   geometry

The example dataset includes **eight activity points** in total.


routes.shp
^^^^^^^^^^

Line dataset representing **precomputed shortest routes** between each
individual's home location and their activity points.

Routes were calculated beforehand using a routing algorithm on a road
network.

Attributes include::

   uid
   DESTid
   geometry

Each route connects a home location with a corresponding activity point.


Test Workflow
-------------

The file ``run_tests.py`` demonstrates a complete workflow using
ActivitySpace Tools.

The script performs the following steps:

1. Load spatial datasets

   * home locations
   * activity locations (EEPs)
   * travel routes

2. Compute **distance-to-home metrics**

   The Spider model calculates the distance between each activity
   location and the individual's home.

3. Generate **activity space polygons**

   The Home Range model constructs an activity space polygon for
   each individual using home locations and activity points.

4. Generate **exposure surfaces**

   The IREM (Individualized Residential Exposure Model) produces
   raster exposure surfaces based on:

   * home locations
   * activity locations
   * travel routes

5. Summarize raster exposure

   Exposure values are summarized for each individual.

6. Compute geometry metrics

   Geometric properties of the resulting activity space polygons
   are calculated.

7. Convert exposure rasters to polygons

   Raster exposure surfaces can be converted into polygons using
   percentile thresholds.


Purpose
-------

These files are intended only for:

* testing library functionality
* demonstrating example workflows
* providing reproducible examples

The dataset is intentionally small so that the entire workflow can
be executed quickly.
