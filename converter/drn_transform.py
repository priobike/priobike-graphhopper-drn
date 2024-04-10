import datetime
import re

import logging
import subprocess
from collections import defaultdict
from typing import List, Set, Tuple

from lxml import etree
from lxml.etree import Element

from epsg_converter import Converter
from mapping import *
from utils import get_bool_variable, haversine

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

Latitude = float
Longitude = float
BoundingBox = Tuple[Latitude, Longitude, Latitude, Longitude]
Coordinate = [Latitude, Longitude]


load_dotenv()
DRN_FILEPATH = os.getenv('DRN_FILEPATH')
TRANSFORMED_DRN_FILEPATH = os.getenv("TRANSFORMED_DRN_FILEPATH")
ENABLE_TRAVELLING_ONEWAY = get_bool_variable("ENABLE_TRAVELLING_ONEWAY")
ONEWAY_TRAVEL_BY_SETTING_MAX_SPEED = get_bool_variable("ONEWAY_TRAVEL_BY_SETTING_MAX_SPEED")
OSM_RESULT_FILE_PATH = os.getenv("OSM_FILEPATH") or "./resources/osm_with_hamburg_cut_out_medium.osm"

def transform_drn_to_osm(occupied_osm_ids: Set[int]):
    transformer = MapTransformer(DRN_FILEPATH, occupied_osm_ids)
    transformer.transform()
    transformer.write_osm_tree_to_file()


class MapTransformer:
    TIMESTAMP = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

    def __init__(self, drn_map_file_path: str, occupied_osm_ids: Set[int]):
        self.drn_tree = etree.parse(drn_map_file_path)
        self.cleanup_namespaces()

        self.osm_tree = etree.Element("osm", version="0.6", generator="DRN_Map_Transformer")
        
        self.occupied_osm_ids = occupied_osm_ids
        
        self.current_way_id = 0
        self.current_node_id = 0
        self.current_relation_id = 0

        self.nodes: Dict[Coordinate, Element] = dict()
        self.nodes_by_own_id: Dict[str, Element] = dict()
        self.nodes_by_pg_id: Dict[str, Element] = dict()


        self.ways: List[Element] = []
        self.relations: Dict[str, List[str]] = defaultdict(lambda: [])
        self.bounding_box: BoundingBox = (1000.0, 1000.0, -1000.0, -1000.0)

        # mapping source and destination ids to node ids
        # attention: even though the node id (src, destination) might be the same
        # the coordinates can slightly differ therefore each src/dest id associated
        # with a list of potential nodes
        self.src_target_to_avg_coord: Dict[str, Coordinate] = defaultdict(set)
        self.src_target_pairs_without_geometry: Dict[Element, Tuple] = dict()

        self.converter = Converter("epsg:25832", "epsg:4326")

        self.way_without_geometry_count = 0
        self.total_count = 0
        self.never_referenced_count = 0
        self.no_highway_count = 0

        self.rounding_coords_max_distance = 0

    def cleanup_namespaces(self):
        for elem in self.drn_tree.getiterator():
            if not (isinstance(elem, etree._Comment) or isinstance(elem, etree._ProcessingInstruction)):
                elem.tag = etree.QName(elem).localname
        etree.cleanup_namespaces(self.drn_tree)

    def get_next_way_id(self) -> str:
        self.current_way_id += 1
        while self.current_way_id in self.occupied_osm_ids:
            self.current_way_id += 1
        return str(self.current_way_id)

    def get_next_node_id(self) -> str:
        self.current_node_id += 1
        while self.current_node_id in self.occupied_osm_ids:
            self.current_node_id += 1
        return str(self.current_node_id)

    def get_next_relation_id(self) -> str:
        self.current_relation_id += 1
        while self.current_relation_id in self.occupied_osm_ids:
            self.current_relation_id += 1
        return str(self.current_relation_id)

    def generate_src_target_to_avg_coordinate_map(self, feature_members):
        # generate map with src target ids and averaged coordinate
        print("Preprocessing Src and Target Ids")
        src_target_to_coordinate_set: Dict[str, List] = defaultdict(list)

        for feature_member in feature_members:
            feature = feature_member[0]
            geom = feature.findall("geom")
            if len(geom) == 0:
                continue
            src_id = feature.findall("source")[0].text
            target_id = feature.findall("target")[0].text

            line_string = geom[0][1] if isinstance(geom[0][0], etree._Comment) else geom[0][0]
            if "NaN" in line_string[0].text:
                logger.warning(f"Generating src-target to average coordinate map: 'NaN' in line string from source: {src_id} to target: {target_id} -> Skipping feature")
                continue
            # coordinates of points defining the way [lat, lon, lat, lon, ...]
            positions = line_string[0].text.split(" ")
            it = iter(positions)
            curr_coord_in_geometry = 0
            total_coord_in_geometry = int(len(positions) / 2)
            for lat_epsg_25832 in it:
                curr_coord_in_geometry += 1
                lon_epsg_25832 = next(it)
                lat_epsg_4326, lon_epsg_4326 = self.converter.convert((float(lat_epsg_25832), float(lon_epsg_25832)))
                lat_epsg_4326 = round(lat_epsg_4326, 7)
                lon_epsg_4326 = round(lon_epsg_4326, 7)
                coord = lat_epsg_4326, lon_epsg_4326

                if curr_coord_in_geometry == 1:
                    src_id = feature.findall("source")[0].text
                    src_target_to_coordinate_set[src_id].append(coord)
                if curr_coord_in_geometry == total_coord_in_geometry:
                    target_id = feature.findall("target")[0].text
                    src_target_to_coordinate_set[target_id].append(coord)

        print("Averaging coordinates")

        for src_target_id, coords in src_target_to_coordinate_set.items():
            lat_avg = round(sum([coord[0] for coord in coords]) / len(coords), 7)
            lon_avg = round(sum([coord[1] for coord in coords]) / len(coords), 7)

            # calculate what the maximum distance between rounded coord and actual position
            max_dist = max([haversine(lon_avg, lat_avg, coord[1], coord[0]) for coord in coords]) * 1000
            if max_dist > self.rounding_coords_max_distance:
                self.rounding_coords_max_distance = max_dist

            self.src_target_to_avg_coord[src_target_id] = (str(lat_avg), str(lon_avg))

    def transform(self):
        feature_members = self.drn_tree.getroot()

        self.generate_src_target_to_avg_coordinate_map(feature_members)
        logger.info(f"Maximum rounding distance between coord and rounded coord for source/target id: {self.rounding_coords_max_distance}")

        for feature_member in feature_members:
            self.parse_element(feature_member[0])

        bb = self.bounding_box
        etree.SubElement(self.osm_tree, "bounds", minlat=str(bb[0]), minlon=str(bb[1]), maxlat=str(bb[2]), maxlon=str(bb[3]))

        for node in self.nodes.values():
            self.osm_tree.append(node)

        for way in self.ways:
            self.osm_tree.append(way)

        for name, members in self.relations.items():
            relation = etree.Element("relation", id=self.get_next_relation_id(), version="1", timestamp=self.TIMESTAMP)
            for member in members:
                etree.SubElement(relation, "member", {"type": "way", "ref": member, "role": ""})
            # tags to mark the bicycle route
            etree.SubElement(relation,  "tag", {"k": "name", "v": name})
            etree.SubElement(relation,  "tag", {"k": "type", "v": "route"})
            etree.SubElement(relation, "tag", {"k": "route", "v": "bicycle"})
            etree.SubElement(relation, "tag", {"k": "network", "v": "lcn"})
            etree.SubElement(relation,  "tag", {"k": "lcn", "v": "yes"})

            self.osm_tree.append(relation)

        logger.info(f"No highway was set and now using default: {self.no_highway_count}")
        logger.info(f"Without geometry: {self.way_without_geometry_count} total: {self.total_count} percentage: {self.way_without_geometry_count * 1.0 / (self.total_count * 1.0)}")
        logger.info(f"Never referenced: {self.never_referenced_count}")

    def parse_element(self, feature: Element):
        self.total_count += 1
        copy_way = False

        way = etree.Element("way", id=self.get_next_way_id(), version="1", timestamp=self.TIMESTAMP)

        self._parse_geometry(way, feature)

        for element in feature:
            if "status" in element.tag:
                pass
            elif "strassenname" in element.tag:
                #way_attributes["name"] = element.text
                etree.SubElement(way, "tag", {"k": "name", "v": element.text})
            elif "radweg_art" in element.tag:
                #tags = radweg_art_to_osm_tags(element.text)
                #way_attributes.update(tags)
                for tag, value in radweg_art_to_osm_tags(element.text).items():
                    etree.SubElement(way, "tag", {"k": tag, "v": value})
            elif "richtung" == element.tag:
                for tag, value in richtung_to_osm_tags(element.text).items():
                    etree.SubElement(way, "tag", {"k": tag, "v": value})
                    if tag == "oneway" and value == "yes":
                        copy_way = True
            elif "oberflaeche" in element.tag:
                for tag, value in oberflaeche_to_osm_tags(element.text).items():
                    etree.SubElement(way, "tag", {"k": tag, "v": value})
            elif "breite" in element.tag:
                width_str = element.text
                if float(width_str) >= 50:
                    width_str = str(float(width_str) / 10.0)
                etree.SubElement(way, "tag", {"k": "width", "v": width_str})
            elif "niveau" in element.tag:
                for tag, value in niveau_to_osm_tags(element.text).items():
                    etree.SubElement(way, "tag", {"k": tag, "v": value})
            elif "source" in element.tag or "target" in element.tag:
                # todo decide if this info is relevant
                pass
                # node_id = self.BASE_ID + int(element.text)
                # if node_id not in self.nodes:
                #     self.nodes[node_id] = etree.Element("node", id=str(node_id))
            elif "geom" in element.tag:
                # already handled
                pass

            elif "radrouten" == element.tag:
                routes = element.text.split(", ")
                way_id = way.attrib["id"]
                for route in routes:
                    self.relations[route].append(way_id)
            elif "fuehrungsart" == element.tag:
                # uncertain if tags with similar meaning exist in osm
                pass
            elif "benutzungspflicht" == element.tag:
                # todo detect traffic sign from it
                pass
            elif "zeitbeschraenkung" == element.tag:
                # could check if in combination with time restricted fußgängerzone - would require standardized
                # time-format to be feasible
                pass

            # the following remaining attributes are redundant and/or don't add new relevant information
            # mofa_frei:  is not relevant
            # hindernis:  information already contained by other tags as "breite" and "radweg_art"
            elif element.tag in ["klasse", "klasse_id", "netzklasse", "zweirichtung", "mofa_frei", "hindernis", "radweg_in_mittellage"]:
                pass
            else:
                raise ValueError(f"Unknown tag found, was: '{element.tag}' with value '{element.text}'")

        #  check if there are nd elements contained, if not the way must not be added
        if len(way.findall("nd")) == 0:
            return

        # fallback for features not setting a radweg_art and therefore wouldn't set a highway, otherwise
        # it would be excluded by graphhopper
        if len(feature.findall("radweg_art")) == 0:
            etree.SubElement(way, "tag", {"k": "highway", "v": "tertiary"})
            self.no_highway_count += 1

        # one-ways should be allowed as segments where one can dismount to traverse the opposite direction, since not
        # possible with current graphhopper create a duplicated 'virtual' geometry which is a footway on top of the
        # oneway
        if copy_way and ENABLE_TRAVELLING_ONEWAY and not ONEWAY_TRAVEL_BY_SETTING_MAX_SPEED:
            way_2 = etree.Element("way", id=self.get_next_way_id(), version="1", timestamp=self.TIMESTAMP)
            self._parse_geometry(way_2, feature)
            vals = {"highway": "footway"}
            for tag, value in vals.items():
                etree.SubElement(way_2, "tag", {"k": tag, "v": value})
            self.ways.append(way_2)

        self.ways.append(way)

        if self.current_way_id % 10000 == 0:
            logger.debug(f"Finished processing Element, curr wayid: {self.current_way_id}")

    def _parse_geometry(self, way, feature):
        """ parse a features geometry and enrich the given way by creating nodes referencing it accordingly """
        geom = feature.findall("geom")
        if len(geom) > 0:
            line_string = geom[0][1] if isinstance(geom[0][0], etree._Comment) else geom[0][0]
            if "NaN" in line_string[0].text:
                logger.warning(f"Parsing geometry: 'NaN' in line string from source: {feature.findall('source')[0].text} to target: {feature.findall('target')[0].text} -> Skipping feature")
                return
            # coordinates of points defining the way [lat, lon, lat, lon, ...]
            positions = line_string[0].text.split(" ")
            it = iter(positions)
            curr_coord_in_geometry = 0
            total_coord_in_geometry = int(len(positions) / 2)
            for lat_epsg_25832 in it:
                curr_coord_in_geometry += 1
                lon_epsg_25832 = next(it)

                lat_epsg_4326, lon_epsg_4326 = self.converter.convert((lat_epsg_25832, lon_epsg_25832))
                lat_epsg_4326 = round(lat_epsg_4326, 7)
                lon_epsg_4326 = round(lon_epsg_4326, 7)
                coord = lat_epsg_4326, lon_epsg_4326

                # source id is only defined for first and last coord in coord list
                if curr_coord_in_geometry == 1:
                    src_id = feature.findall("source")[0].text
                    # set the coordinate to the rounded one instead of the one specified through the list of coordinates
                    coord = self.src_target_to_avg_coord[src_id]
                if curr_coord_in_geometry == total_coord_in_geometry:
                    target_id = feature.findall("target")[0].text
                    coord = self.src_target_to_avg_coord[target_id]

                if coord not in self.nodes:
                    node_id = self.get_next_node_id()
                    node = etree.Element("node", id=node_id, version="1", timestamp=self.TIMESTAMP,
                                         lat=str(lat_epsg_4326), lon=str(lon_epsg_4326))

                    self.nodes[coord] = node

                    self._update_bounding_box(lat_epsg_4326, lon_epsg_4326)

                node_id = self.nodes[coord].attrib["id"]
                etree.SubElement(way, "nd", {"ref": node_id})
        else:
            # there are features that don't define a geometry and therefore can't be used, just keep track of them
            self.way_without_geometry_count += 1
            src_target = feature.findall("source")[0].text, feature.findall("target")[0].text
            self.src_target_pairs_without_geometry[way] = src_target

    def _update_bounding_box(self, lat_epsg_4326, lon_epsg_4326):
        """ when parsing a new node it could be that the overall bounding box of the resulting
        dataset needs to be increased """
        self.bounding_box = (
            min(self.bounding_box[0], lat_epsg_4326),
            min(self.bounding_box[1], lon_epsg_4326),
            max(self.bounding_box[2], lat_epsg_4326),
            max(self.bounding_box[3], lon_epsg_4326),
        )

    def write_osm_tree_to_file(self):
        tree = self.osm_tree.getroottree()
        tree.write(TRANSFORMED_DRN_FILEPATH, encoding='utf-8', xml_declaration=True, pretty_print=True)
        logger.info("Sort resulting file.")
        subprocess.run([f'osmium sort {TRANSFORMED_DRN_FILEPATH} -o {TRANSFORMED_DRN_FILEPATH} --overwrite'], shell=True)

def gather_occupied_osm_ids():
    osm_file_path = OSM_RESULT_FILE_PATH
    with open(osm_file_path, "r") as file:
        osm_xml_data = file.read()
    occupied_ids = re.findall(r"\"[0-9]+\"", osm_xml_data)
    unique_occupied_ids = set()
    for id in occupied_ids:
        unique_occupied_ids.add(int(id.replace("\"", "")))
    return unique_occupied_ids

if __name__ == '__main__':
    occupied_osm_ids = gather_occupied_osm_ids()
    transform_drn_to_osm(occupied_osm_ids)
