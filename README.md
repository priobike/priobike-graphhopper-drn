# GraphHopper-DRN

Credit: Max Lorenz

# Overview

## Graphhopper Configurations for DRN, OSM and Map-Conflated

This directories contain dependencies to build working GraphHopper images. 

## Converter 

Python project responsible for conversions on used datasets and creation of intermediate datasets.

### DRN GML to OSM format transformation (`drn_transform.py)

Tool to convert Hamburgs dataset "Digitales Radverkehrsnetz" (DRN) to the osm format.
Done by mapping information as close as possible to osm equivalents.

If reverse oneway travel should be allowed it can be activated by setting an environmental variable:

`ENABLE_TRAVELLING_ONEWAY=[true|false]`

Should this be activated also the approach used can be set. Using the maxspeed setting currently 
requires an adjustment in graphhopper itself. 
If deactivated geometries for reverse directions will be created.

`ONEWAY_TRAVEL_BY_SETTING_MAX_SPEED=[true|false]`

### Map Conflation (`main.py`)
Starting with a drn dataset in gml format and osm dataset go through all required steps to 
create a conflated dataset containing DRN data inside Hamburg and OSM data outside. 

For debugging intermediary steps could also be executed manually.
Conflation is done through the following steps:

- `osm_extract.py` prepares an osm dataset of the region outside Hamburg: 
  - removes ways inside Hamburg
  - cut ways on the boundary of HH and keep only the part outside
- `postgis_connector.py` finds matches between drn nodes close to border and osm ways
- `conflation.py` conflates OSM dataset and transformed DRN dataset via the previously found matches

#### Dependendcies
- uses poetry to manage python dependencies 
- requires PostgreSQL to be installed for finding matches (database creation and enabling postgis is done automatically during the conflation process)

### Further Tools
- `graphhopper_route_to_sg_selector_request.py` - convert a graphhopper route to a format used by SG-Selector 
- `map_statistics.py` - collect metrics on a specified osm file (e.g. number of ways, total distance, etc.)
- `sg_selector_eval.py` - using paths based on drn and osm routes request matched connections by sg-selector and format the results
- `similarity.py` - calculate hausdorff-metrik and average distance between test-routes and their osm and drn equivalents
- `snapping_distance_meassuring.py` - calculating random routes compare average snapping distances between osm and drn variants
- `osm_extract.py` - extract an OSM region which contains ways outside of Hamburg but not within Hamburg