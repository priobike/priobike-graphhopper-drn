import logging
import os
import subprocess
from datetime import datetime

from dotenv import load_dotenv
from lxml import etree
from map_conflation import (create_node_id_to_coordinate_mapping,
                            get_node_ids_for_osm_way, load_osm_xml_data)
from postgis_connector import (boundary_line_as_32633, create_db,
                               open_connection, update_projection)
from shapely.geometry import Point
from shapely.geometry.polygon import LineString, Polygon
from utils import (get_boundary_hamburg, get_osm_2_psql_host_param,
                   get_psql_host_param)

"""
extract an osm region which contains ways outside of hamburg but not within hamburg

using osmium or merging datasets surrounding hamburg wouldn't work because their
border is not exactly on the city boundary, but instead overlapping
"""

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

load_dotenv()

osm_2_psql_host_param = get_osm_2_psql_host_param()

# OSM_FILE_PATH = "./resources/hamburg-latest_2022_05_16.osm"
OSM_FILE_PATH = os.getenv("OSM_ORIGINAL_FILEPATH") or "./resources/hamburg_with_surroundings_medium.osm"
OSM_RESULT_FILE_PATH = os.getenv("OSM_FILEPATH") or "./resources/osm_with_hamburg_cut_out_medium.osm"


def extract_region_outside_hh():
    logger.info("extract region outside hamburg")

    time_start = datetime.now()

    simple_poly_1 = Polygon([[9.83, 53.47], [9.83, 53.59], [10.14, 53.59], [10.14, 53.47]])
    simple_poly_2 = Polygon([[9.92, 53.57], [9.92, 53.62], [10.13, 53.63], [10.13, 53.57]])

    logger.info("Loading Hamburg boundary")
    hamburg_boundary = Polygon(get_boundary_hamburg())

    osm_file_path = OSM_FILE_PATH
    osm_xml_data = etree.parse(osm_file_path)

    root = osm_xml_data.getroot()
    logger.info(f"Loaded XML File with elements: {len(root)} ({datetime.now() - time_start})")

    # we need to iterate twice
    # first go is to create a map of node ids, to coordinates
    # second iteration is to go through every way build their geometry and test if the way should be excluded or cut

    logger.info("started indexing nodes and coordinates")
    node_id_to_coordinate = dict()
    for node_element in root.iterchildren(tag="node"):
        node_id_to_coordinate[node_element.get("id")] = [node_element.get("lat"), node_element.get("lon")]
    logger.info(f"finished indexing nodes and coordinates: {len(node_id_to_coordinate)} ({datetime.now() - time_start})")

    logger.info("started checking ways")
    count = 0
    for way_element in root.iterchildren(tag="way"):
        point_refs = []
        for nd_element in way_element.iterchildren(tag="nd"):
            point_refs.append(nd_element.get("ref"))

        all_inside = True
        for point_ref in point_refs:
            if point_ref not in node_id_to_coordinate:
                break

            point = Point(float(node_id_to_coordinate[point_ref][1]), float(node_id_to_coordinate[point_ref][0]))
            if simple_poly_1.contains(point) or simple_poly_2.contains(point):
                break

            inside = hamburg_boundary.contains(point)
            if not inside:
                all_inside = False
                break

        if all_inside:
            root.remove(way_element)

        count += 1
        if count % 10000 == 0:
            logger.info(f"processed {count} ways ({datetime.now() - time_start})")

    logger.info(f"finished checking ways ({datetime.now() - time_start})")
    tree = root.getroottree()
    tree.write(OSM_RESULT_FILE_PATH, encoding='utf-8', xml_declaration=True, pretty_print=True)


def cut_osm_ways_after_border():
    """
    given an osm file containing ways that cross the given boundary, cut the ways which cross this boundary on the
    first node that is inside the boundary polygon
    """
    logger.info("cut osm ways after border")

    # create postgis db with osm ways as "fast" approach to find ways crossing the border
    subprocess.run([f'osm2pgsql {osm_2_psql_host_param} -d osm_cut --hstore --hstore-add-index {OSM_RESULT_FILE_PATH}'], shell=True)
    conn, curs = open_connection("osm_cut")

    update_projection(curs, conn, "planet_osm_line", "LineString")

    hamburg_boundary_line_as_32633 = boundary_line_as_32633()

    linestring_string = str(hamburg_boundary_line_as_32633)
    curs.execute("""SELECT osm_id from planet_osm_line where st_dwithin(way_32633, 'SRID=32633;%s'::geometry, %s);""" % (linestring_string, 0))
    osm_ways_on_border = curs.fetchall()
    osm_ways_on_border = list(filter(lambda osm_id: osm_id > 0, [rec[0] for rec in osm_ways_on_border]))

    #
    # with found osm ways on border go through the osm file and split ways from osm_ids found through postgis
    #

    osm_xml_data = load_osm_xml_data(OSM_RESULT_FILE_PATH)
    osm_root = osm_xml_data.getroot()
    osm_node_coord_mapping = create_node_id_to_coordinate_mapping(osm_xml_data)
    boundary_ls = LineString(get_boundary_hamburg())

    count_idx = 0
    logger.info(f"Cutting {len(osm_ways_on_border)} ways")
    for way_id in osm_ways_on_border:
        osm_way_ele = osm_root.find(f"way[@id='{way_id}']")
        if osm_way_ele is None:
            logger.info(f"osm way with id {way_id} not found in loaded dataset")
        node_ids = get_node_ids_for_osm_way(osm_xml_data, way_id)

        logger.info(f"Cutting way {way_id} ({count_idx})")
        count_idx += 1
        node_coord = osm_node_coord_mapping[node_ids[0]]
        is_last_inside = boundary_ls.contains(Point(node_coord))
        for idx in range(1, len(node_ids)):
            # check on which node the border is crossed and throw away everything before or after
            node_id = node_ids[idx]
            if node_id not in osm_node_coord_mapping:
                break
            node_coord = osm_node_coord_mapping[node_id]
            is_inside = boundary_ls.contains(Point(node_coord))
            if is_inside != is_last_inside:
                if is_last_inside:
                    # throw away points before
                    for idx2 in range(0, idx):
                        del_node_id = node_ids[idx2]
                        nd_ele = osm_way_ele.find(f"nd[@ref='{del_node_id}']")
                        osm_way_ele.remove(nd_ele)
                else:
                    # throw away points coming after
                    if idx == len(node_ids) - 1:
                        # we are already at the last node and there nothing to delete comes after it
                        continue
                    for idx2 in range(idx + 1, len(node_ids)):
                        del_node_id = node_ids[idx2]
                        nd_ele = osm_way_ele.find(f"nd[@ref='{del_node_id}']")
                        osm_way_ele.remove(nd_ele)

                # way got split continue with the next one
                break

    out_file_name = OSM_RESULT_FILE_PATH
    osm_xml_data.write(out_file_name, encoding='utf-8', xml_declaration=True, pretty_print=True)

    conn.close()
    subprocess.run([f'dropdb {get_psql_host_param()} osm_cut'], shell=True)


if __name__ == '__main__':
    create_db('osm_cut')
    extract_region_outside_hh()
    cut_osm_ways_after_border()
