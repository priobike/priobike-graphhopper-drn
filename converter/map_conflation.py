import json
import math
import os
import subprocess
import time
from datetime import datetime
from typing import Dict, List
import logging

from dotenv import load_dotenv
from lxml import etree
from lxml.etree import ElementTree
from shapely.geometry import LineString
from shapely.ops import transform
from functools import partial
import pyproj


from drn_transform import haversine
from utils import get_boundary_hamburg

"""
given drn-osm-node-ids and an osm-way-id matching candidate, search for the point
in the way for osm-way-id being the closest to drn-osm-node-id node. This node
is now a replacement for the drn-osm-node-id node. All occurrences of drn-osm-node-id
will be replaced by the found osm-node-id.
"""

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

start_time = time.time()

INSERT_SUPPORT_POINTS = True

load_dotenv()

DRN_FILE_PATH = os.getenv("TRANSFORMED_DRN_FILEPATH") or "./resources/drn_as_osm.osm"
OSM_FILE_PATH = os.getenv("OSM_CUT_FILEPATH") or "./resources/osm_with_hamburg_cut_out_medium.osm"
MATCHES_FILE_PATH = os.getenv("MATCHES_FILE_PATH") or "./conflation/matches_concept_2_medium.json"

OUT_FILE_PATH = "resources/osm_with_drn_conflated.osm"
AUXILIARY_POINTS_FILE_PATH = "conflation/helper_points_medium.geojson"


def get_hamburg_boundary_line_string() -> LineString:
    hamburg_boundary_line = LineString(get_boundary_hamburg())
    project = partial(
        pyproj.transform,
        pyproj.Proj('EPSG:4326'),
        pyproj.Proj('EPSG:32633'),
        always_xy=True
    )
    hamburg_boundary_line_projected = transform(project, hamburg_boundary_line)
    return hamburg_boundary_line_projected


def conflate():
    logger.info(f"Load data files and create acceleration data structures ({round(time.time() - start_time, 2)}s)")

    with open(MATCHES_FILE_PATH) as f:
        matches = json.load(f)

    drn_xml_data = load_osm_xml_data(DRN_FILE_PATH)
    osm_xml_data = load_osm_xml_data(OSM_FILE_PATH)

    insert_osm_helper_points(osm_xml_data, matches)

    drn_node_coord_mapping = create_node_id_to_coordinate_mapping(drn_xml_data)
    osm_node_coord_mapping = create_node_id_to_coordinate_mapping(osm_xml_data)

    logger.info(f"Start conflation of {len(matches.keys())} items ({round(time.time() - start_time, 2)}s)")

    ix = 0
    for drn_node_id, osm_matches in matches.items():
        if ix % 25 == 0:
            logger.info(f"Matched {ix} elements")
        ix += 1

        drn_node_coord = drn_node_coord_mapping[drn_node_id]
        osm_way_id = osm_matches[0][0]

        node_ids = get_node_ids_for_osm_way(osm_xml_data, osm_way_id)
        if len(node_ids) == 0:
            continue

        # select closest node from precomputed node to coord data struct
        min_distance = 100_000_000
        min_distance_osm_node_id = -1

        for i in range(len(node_ids)):
            node_id = node_ids[i]
            osm_node_coord = osm_node_coord_mapping[node_ids[i]]
            distance = haversine(*osm_node_coord, *drn_node_coord)
            if distance < min_distance:
                min_distance = distance
                min_distance_osm_node_id = node_id

        min_distance_meter = min_distance * 1000
        if min_distance_meter > 8:
            logger.info(f"skip {drn_node_id} because it's to far away from it's match ({min_distance_meter}m, osm way id {osm_way_id})")
            continue
        else:
            logger.info(f"matched osm way {osm_way_id}")

        # update all occurrences of node id in drn data set
        nd_references = drn_xml_data.xpath(f"way/nd[@ref='{drn_node_id}']")
        for nd_ref in nd_references:
            nd_ref.set("ref", str(min_distance_osm_node_id))

    logger.info(f"append drn data to osm data file ({round(time.time() - start_time, 2)}s)")
    append_osm_xml_data(osm_xml_data, drn_xml_data)

    logger.info(f"write resulting osm data to file ({round(time.time() - start_time, 2)}s)")
    out_file_name = OUT_FILE_PATH
    osm_xml_data.write(out_file_name, encoding='utf-8', xml_declaration=True, pretty_print=True)
    # make sure osm file is properly ordered since import in graphhopper fails otherwise
    subprocess.run([f"osmium sort ./{out_file_name} -o ./{out_file_name} --overwrite"], shell=True)


def get_node_ids_for_osm_way(osm_xml_data, osm_way_id) -> List[int]:
    osm_way_ele = osm_xml_data.xpath(f"way[@id='{osm_way_id}']")
    if len(osm_way_ele) == 0:
        logger.info(f"no way with id {osm_way_id} found")
        return []
    osm_way_ele = osm_way_ele[0]
    node_ids = []
    for nd_ref_ele in osm_way_ele.iterchildren("nd"):
        node_ids.append(nd_ref_ele.get("ref"))
    return node_ids


def insert_osm_helper_points(osm_xml_data, matches: Dict):
    proj_to_32633 = get_projection_32633()
    proj_to_4326 = get_projection_4326()
    osm_node_coord_mapping = create_node_id_to_coordinate_mapping(osm_xml_data)
    hamburg_boundary_line_string = get_hamburg_boundary_line_string()

    helper_point_id = 999_999_999_999_999_999
    geojson = {"type": "GeometryCollection", "geometries": []}

    logger.info(f"Insert auxiliary points {len(matches.keys())} ({round(time.time() - start_time, 2)}s)")

    osm_way_ids = [match[0][0] for match in matches.values()]
    for idx, osm_way_id in enumerate(set(osm_way_ids)):
        if idx % 25 == 0:
            logger.info(f"at {idx}")

        node_ids = get_node_ids_for_osm_way(osm_xml_data, osm_way_id)
        osm_root = osm_xml_data.getroot()
        osm_way_ele = osm_root.find(f"way[@id='{osm_way_id}']")

        if len(node_ids) == 0:
            continue

        for i in range(1, len(node_ids)):
            osm_node_coord = osm_node_coord_mapping[node_ids[i]]
            last_node_coord = osm_node_coord_mapping[node_ids[i - 1]]

            intersecting_segment_32633 = transform(proj_to_32633, LineString([last_node_coord, osm_node_coord]))
            intersection_32633 = hamburg_boundary_line_string.intersection(intersecting_segment_32633)

            if intersection_32633.is_empty:
                continue

            insert_idx = i + 1
            for dist in range(8, math.floor(intersecting_segment_32633.length), 8):
                new_point = intersecting_segment_32633.interpolate(dist)
                new_point_back_projected = transform(proj_to_4326, new_point)
                coords_new = [new_point_back_projected.xy[0][0], new_point_back_projected.xy[1][0]]
                geojson['geometries'].append({"type": "Point", "coordinates": coords_new})

                osm_way_ele.insert(insert_idx, etree.Element("nd", ref=str(helper_point_id)))
                etree.SubElement(osm_root, "node", {
                    "id": str(helper_point_id),
                    "version": "1",
                    "timestamp": datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
                    "lat": str(coords_new[1]),
                    "lon": str(coords_new[0])
                })

                insert_idx += 1
                helper_point_id += 1

    with open(AUXILIARY_POINTS_FILE_PATH, "w") as f:
        json.dump(geojson, f)


def get_projection_32633():
    return partial(
        pyproj.transform,
        pyproj.Proj('EPSG:4326'),
        pyproj.Proj('EPSG:32633'),
        always_xy=True)


def get_projection_4326():
    return partial(
        pyproj.transform,
        pyproj.Proj('EPSG:32633'),
        pyproj.Proj('EPSG:4326'),
        always_xy=True)


def load_osm_xml_data(filepath: str) -> ElementTree:
    return etree.parse(filepath)


def create_node_id_to_coordinate_mapping(xml: ElementTree):
    node_id_to_coordinate = dict()
    for node_element in xml.getroot().iterchildren(tag="node"):
        node_id_to_coordinate[node_element.get("id")] = (float(node_element.get("lon")), float(node_element.get("lat")))
    return node_id_to_coordinate


def append_osm_xml_data(osm_xml_data: ElementTree, additional_xml_data: ElementTree):
    osm_xml_root = osm_xml_data.getroot()
    for ele in additional_xml_data.getroot().iterchildren():
        osm_xml_root.append(ele)


if __name__ == '__main__':
    conflate()
