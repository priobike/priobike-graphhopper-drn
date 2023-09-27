# 🚴‍♂️ GraphHopper-DRN: GraphHopper for the Digitales Radverkehrsnetz (DRN) dataset of Hamburg.

```bibtex
@inproceedings{matthes2023accurate,
  title={Accurate Bike Routing for Lane Prediction in GLOSA Apps via Infrastructure Reference Models},
  author={Matthes, Philipp and Springer, Thomas and Daniel, Jeschor},
  booktitle={2023 IEEE International Conference on Intelligent Transportation Systems (ITSC)},
  pages={1--6},
  year={2023},
  organization={IEEE}
}
```

For DGM Support see https://github.com/priobike/priobike-graphhopper-dgm

Welcome to our custom GraphHopper routing engine! This powerful routing engine allows you to calculate optimized routes and navigation instructions based on various transportation modes, such as driving, cycling, or walking. 

The routing foundation is optimized for bicycles and is based on the [Digitales Radverkehrsnetz (DRN)](https://metaver.de/trefferanzeige?docuuid=EA847D9F-6403-4B75-BCDB-73F831F960C7) dataset of Hamburg. The DRN dataset is a collection of all bicycle paths in Hamburg and is provided by the Behörde für Verkehr und Mobilitätswende, (BVM).

In this way, it is tailored for high-precision bike routing. We use this system for our navigation app for cyclists, to obtain highly precise routes for green light optimal speed advisory (GLOSA). However it can also be used for other purposes.

## Features

- Optimized Routing: Calculate the most efficient routes for bicycles in Hamburg using the DRN dataset.
- Multiple Transportation Modes: Choose between different transportation modes, including cycling, driving, and walking. You may also choose between different types of bicycles, such as city bikes, mountain bikes, or racing bikes.
- Turn-by-Turn Navigation: Get detailed navigation instructions for each step of the route.
- Customizable Routing Profiles: Customize the routing profiles to suit your specific needs and preferences.
- Fast and Scalable: Benefit from the speed and scalability of the GraphHopper routing engine.
- Many more: See the [GraphHopper documentation](https://docs.graphhopper.com/) for more features.

## Examples

Here's an example of how to calculate a bike route using the GraphHopper-DRN API:

```
curl "http://localhost:8989/route?profile=bike_default&point=53.5511,9.9937&point=53.5449,10.0059"
```

This request calculates a bike route between the coordinates 53.5511,9.9937 and 53.5449,10.0059. For more examples and information, see the [GraphHopper documentation](https://docs.graphhopper.com/).

## Quickstart

We provide a Docker image for easy deployment. To get started, simply run the following command:

```
docker build -t graphhopper-drn .
docker run -p 8989:8989 graphhopper-drn
```

The `docker build` step will perform all necessary data preprocessing and routing database preheating. The final image is ready-to-use and can be started with `docker run`. The routing engine will be available at `http://localhost:8989`.

## License

GraphHopper-DRN is released under the MIT License.

## The Authors

Philipp Matthes, Thomas Springer, Daniel Jeschor. Additional credit: Max Lorenz. This project is currently considered for publication. Citation information will follow.

## Technical Details for the Converter

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
