# Test Data and Example Workflow

This folder contains a small example dataset and a test script used to
demonstrate and validate the functionality of the **ActivitySpace Tools**
library.

The dataset is derived from anonymized **Public Participation GIS (PPGIS)**
data originally collected in **Oulu, Finland**. To protect privacy, the data
have been simplified and reduced to a minimal example suitable for testing.

The dataset represents mobility information for **two individuals** and
includes a total of **eight activity markings**.

---

# Files

## `Home.shp`

Point dataset representing the **home locations** of individuals.

Attributes:

- `uid` – unique identifier for each individual
- `geometry` – home location

Each individual has one home location.

---

## `eep.shp`

Point dataset representing **Everyday Errand Points (EEPs)** or
destinations visited by individuals.

These points originate from PPGIS survey responses where participants
marked locations they frequently visit.

Attributes include:

- `uid` – individual identifier
- `DESTid` – destination identifier
- `weight` – reported importance or frequency of the location
- `travelMode` – reported travel mode used to reach the destination
- `geometry` – spatial location of the activity point

The test dataset includes **eight activity points** in total.

---

## `routes.shp`

Line dataset representing **precomputed shortest routes** between each
individual's home location and their reported activity points.

Routes were calculated beforehand using a routing algorithm on a road
network.

Attributes include:

- `uid` – individual identifier
- `DESTid` – destination identifier linking the route to the destination
- `geometry` – route geometry

Each route connects a home location to a corresponding activity point.

---

# Test Workflow

The file `run_tests.py` demonstrates a complete workflow using the
ActivitySpace Tools library.

The script performs the following steps:

1. **Load spatial datasets**

   - home locations (`Home.shp`)
   - activity locations (`eep.shp`)
   - travel routes (`routes.shp`)

2. **Compute distance-to-home metrics**

   The Spider model calculates the distance between each activity
   location and the individual's home.

3. **Generate activity space polygons**

   The Home Range model constructs an activity space polygon for each
   individual using home locations and activity points.

4. **Generate exposure surfaces**

   The IREM (Individualized Residential Exposure Model) generates raster
   exposure surfaces for each individual based on:

   - home locations
   - activity locations
   - routes between them

5. **Summarize raster exposure**

   Exposure values are summarized for each individual.

6. **Compute geometry metrics**

   Geometric properties of the resulting activity space polygons are
   calculated.

7. **Convert exposure rasters to polygons**

   Raster exposure surfaces can be converted to polygons using
   percentile thresholds.

---

# Purpose

These files are intended only for:

- testing library functionality
- demonstrating example workflows
- providing reproducible examples

The dataset is intentionally small so that the full workflow can be
executed quickly.