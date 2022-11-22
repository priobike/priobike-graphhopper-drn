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
