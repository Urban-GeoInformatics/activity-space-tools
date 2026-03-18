ActivitySpace Tools — Example Dataset and Workflow
=================================================

This section describes the example dataset and the complete workflow
included with the ``activityspace`` package.

The package provides:

- ``example_usage.py`` → a ready-to-run script demonstrating the full workflow  
- ``test_data/`` → a small sample dataset for testing and learning  

The example is designed to run out-of-the-box and demonstrates how to
move from raw spatial data to activity spaces, exposure estimates,
and summary metrics.

---

Test Data
---------

The dataset is derived from anonymized Public Participation GIS (PPGIS)
data originally collected in **Oulu, Finland**. To protect privacy, the
data have been simplified and reduced to a minimal example suitable
for testing.

The dataset represents mobility information for two individuals
and includes a total of eight activity markings.

It is intentionally small so that the full workflow can be executed quickly.

---

Data files
----------

The example uses the following files inside ``test_data/``:

::

    test_data/
        eep.shp
        Home.shp
        routes.shp

---

Home.shp
^^^^^^^^

Point dataset representing the home locations of individuals.

Attributes include::

   uid
   geometry

Each individual has one home location.

---

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

---

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

---

Example workflow
----------------

The file ``example_usage.py`` demonstrates a complete workflow using
ActivitySpace Tools.

Running the script performs the following steps:

---

1. Load spatial datasets

   .. code-block:: python

      poi = gpd.read_file(poi_path)
      home = gpd.read_file(home_path)
      routes = gpd.read_file(routes_path)

---

2. Compute distance-to-home metrics (Spider model)

   .. code-block:: python

      spider_out = add_distance_to_home(...)

   Adds:

   - ``dist_m`` → distance from each activity point to home

---

3. Generate activity space polygons (Home Range model)

   .. code-block:: python

      home_range = model_home_range(...)

   Creates one polygon per individual representing their activity space.

---

4. Generate exposure surfaces (IREM model)

   .. code-block:: python

      rasters = run_irem(...)

   Produces raster exposure surfaces based on:

   - home locations  
   - activity locations  
   - travel routes  

---

5. Summarize raster exposure

   .. code-block:: python

      summary = summarize_rasters(...)

   Outputs metrics such as mean and total exposure.

---

6. Compute exposure and geometry metrics

   .. code-block:: python

      exposure = exposure_summary(...)
      geom = as_geometry_calculator(...)

   Produces:

   - exposure summaries linked to activity spaces  
   - geometric properties (area, perimeter, etc.)

---

7. Convert exposure rasters to polygons

   .. code-block:: python

      irem_polygons = irem_rasters_to_polygons(...)

   Creates polygons representing areas of higher exposure.

---

Outputs
-------

All results are written to:

::

    test_output/

Including:

- distance metrics  
- activity space polygons  
- exposure rasters  
- summary tables  
- geometry metrics  
- exposure polygons  

---

Purpose
-------

These files are intended only for:

- testing library functionality  
- demonstrating example workflows  
- providing reproducible examples  

The dataset is simplified and should not be interpreted as a full
research dataset.