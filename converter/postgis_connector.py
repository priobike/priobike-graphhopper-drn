import json
import logging
import os
import subprocess
import time
from functools import partial

import psycopg2
import pyproj
from dotenv import load_dotenv
from drn_insert_node_tag import insert_node_tag
from psycopg2._psycopg import connection, cursor
from shapely.geometry import LineString, Point
from shapely.ops import transform
from utils import (get_boundary_hamburg, get_osm_2_psql_host_param,
                   get_psql_host_param)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

# specifies if databases should be created first and projections etc. be performed on it
# only required on the first run
init = True
# set to true if first concept should be executed, otherwise second approach is used
use_concept_1 = False

load_dotenv()


psql_host = os.getenv("POSTGRES_HOST")
psql_user = os.getenv("POSTGRES_USER")
psql_pass = os.getenv("POSTGRES_PASSWORD")
psql_host_param = get_psql_host_param()
osm_2_psql_host_param = get_osm_2_psql_host_param()

# files must exist beforehand
TRANSFORMED_DRN_FILEPATH = os.getenv("TRANSFORMED_DRN_FILEPATH") or "./resources/drn_as_osm.osm"
OSM_FILE_PATH = os.getenv("OSM_CUT_FILEPATH") or "./resources/osm_with_hamburg_cut_out_medium.osm"

# files will be created during execution
DRN_TMP_FILE_PATH = "./resources/tmp_drn_as_osm.osm"
MATCHES_FILE_PATH = os.getenv("MATCHES_FILE_PATH") or "./conflation/matches_concept_2_medium.json"

def find_matches():
    start_time = time.time()
    if init:
        logger.info("setup db")
        setup_db()

    osm_conn, osm_curs = open_connection("osm")
    drn_conn, drn_curs = open_connection("drn")

    if init:
        # -- initial setup only on first execution
        update_projection(drn_curs, drn_conn, "planet_osm_line", "LineString")
        update_projection(osm_curs, osm_conn, "planet_osm_line", "LineString")
        update_projection(drn_curs, drn_conn, "planet_osm_point", "Point")
        update_projection(osm_curs, osm_conn, "planet_osm_point", "Point")
        fill_osm_db_with_drn_data(drn_curs, osm_curs, osm_conn)

    if use_concept_1:
        concept_1(osm_curs, start_time)
    else:
        concept_2(osm_curs, start_time)

    osm_conn.close()
    drn_conn.close()
    subprocess.run([f'dropdb {psql_host_param} osm'], shell=True)
    subprocess.run([f'dropdb {psql_host_param} drn'], shell=True)


def concept_1(osm_curs: cursor, start_time):
    """ approach that matches drn ways with osm ways """
    logger.info(f"search drn ways close to border ({round(time.time() - start_time, 2)}s)")
    drn_ways_near_border = ways_close_to_border(osm_curs, "drn_planet_osm_line", 5)

    logger.info(f"start searching matches. Ways to match: {len(drn_ways_near_border)} ({round(time.time() - start_time, 2)}s)")
    drn_way_id_to_matched_osm_ids = calc_way_matches(osm_curs, drn_ways_near_border)
    logger.info(f"finished match search ({round(time.time() - start_time, 2)}s)")

    # store matches for later analysis
    logger.info(f"store matches as geojson files  ({round(time.time() - start_time, 2)}s)")
    res = get_geojson_for_drn_matches(osm_curs, drn_way_id_to_matched_osm_ids)
    with open("./conflation/drn_matches.geojson", "w") as f:
        json.dump(res, f)
    res = get_geojson_for_osm_matches(osm_curs, drn_way_id_to_matched_osm_ids)
    with open("./conflation/osm_matches.geojson", "w") as f:
        json.dump(res, f)
    with open("./conflation/matches_concept_1.json", "w") as f:
        json.dump(res, f)


def concept_2(osm_curs: cursor, start_time: float):
    """ approach that matches one point for a drn way with osm ways """

    # retrieve drn nodes near border
    logger.info(f"search drn nodes close to border ({round(time.time() - start_time, 2)}s)")
    drn_nodes_near_border = nodes_close_to_border(osm_curs, "drn_planet_osm_point", 20)

    # match found nodes with osm ways
    logger.info(f"start searching matches. Ways to match: {len(drn_nodes_near_border)} ({round(time.time() - start_time, 2)}s)")
    drn_id_to_matched_osm_ids = calc_point_matches(osm_curs, drn_nodes_near_border)

    # store results for visualization and later use
    logger.info(f"store matches as geojson files  ({round(time.time() - start_time, 2)}s)")
    geojson = drn_nodes_to_geojson(osm_curs, drn_nodes_near_border)
    with open("./conflation/drn_node_near_border.geojson", "w") as f:
        json.dump(geojson, f)
    res = get_geojson_for_osm_matches(osm_curs, drn_id_to_matched_osm_ids)
    with open("./conflation/osm_matches_for_drn_points.geojson", "w") as f:
        json.dump(res, f)
    with open(MATCHES_FILE_PATH, "w") as f:
        json.dump(drn_id_to_matched_osm_ids, f)


def calc_point_matches(osm_curs: cursor, drn_nodes_near_border):
    """ match found drn nodes with osm ways """
    drn_id_to_matched_osm_ids = dict()

    for idx, node in enumerate(drn_nodes_near_border):
        query = f"""select ol.osm_id, st_distance(dp.way_32633, ol.way_32633) as distance 
                           from planet_osm_line as ol 
                           cross join drn_planet_osm_point as dp 
                           where dp.osm_id = {node[0]} 
                           and ol.highway is not null 
                           order by distance limit 5;"""
        osm_curs.execute(query)
        matched_ways = osm_curs.fetchall()
        max_idx = min(1, len(matched_ways))
        drn_id_to_matched_osm_ids[node[0]] = matched_ways[:max_idx]
        if idx % 10 == 0:
            logger.info(f"{round(idx / len(drn_nodes_near_border) * 100, 2)} %")

    return drn_id_to_matched_osm_ids


def calc_way_matches(osm_curs: cursor, drn_ways_near_border):
    drn_id_to_matched_osm_ids = dict()

    for idx, way in enumerate(drn_ways_near_border):
        query = f"""select ol.osm_id, st_distance(dl.way_32633, ol.way_32633) as distance 
                       from planet_osm_line as ol 
                       cross join drn_planet_osm_line as dl 
                       where dl.osm_id = {way[0]} 
                       and ol.highway is not null 
                       order by distance limit 50;"""
        osm_curs.execute(query)
        matched_ways = osm_curs.fetchall()
        max_idx = min(1, len(matched_ways))
        drn_id_to_matched_osm_ids[way[0]] = matched_ways[:max_idx]
        if idx % 10 == 0:
            logger.info(round(idx / len(drn_ways_near_border) * 100, 2), "%")

    logger.info(drn_id_to_matched_osm_ids)
    return drn_id_to_matched_osm_ids


def get_geojson_for_drn_matches(curs: cursor, matches):
    """
    transform a given dictionary of matches in form of drn_osm_id: [osm ids] pairs to geojson
    containing the drn way geometries
    """
    drn_geometries = []
    for drn_id, osm_matches in matches.items():
        curs.execute(f"select st_asgeojson(st_transform(way_32633, 4326)) from drn_planet_osm_line where osm_id = {drn_id};")
        drn_geometry = curs.fetchall()[0][0]
        drn_geometries.append(json.loads(drn_geometry))
    geojson = {
        "type": "GeometryCollection",
        "geometries": drn_geometries
    }
    return geojson


def get_geojson_for_osm_matches(curs: cursor, matches):
    """
    transform a given dictionary of matches in form of drn_osm_id: [osm ids] pairs to geojson
    containing the osm way geometries of the first match
    """
    osm_geometries = []
    for drn_id, osm_matches in matches.items():
        curs.execute(f"select st_asgeojson(st_transform(way_32633, 4326)) from planet_osm_line where osm_id = {osm_matches[0][0]};")
        osm_geometry = curs.fetchall()[0][0]
        osm_geometries.append(json.loads(osm_geometry))
    geojson = {
        "type": "GeometryCollection",
        "geometries": osm_geometries
    }
    return geojson


def drn_nodes_to_geojson(curs: cursor, drn_nodes):
    drn_geometries = []
    for rec in drn_nodes:
        drn_id = rec[0]
        curs.execute(
            f"select st_asgeojson(st_transform(way_32633, 4326)) from drn_planet_osm_point where osm_id = {drn_id};")
        drn_geometry = curs.fetchall()[0][0]
        drn_geometries.append(json.loads(drn_geometry))
    geojson = {
        "type": "GeometryCollection",
        "geometries": drn_geometries
    }
    return geojson


def fill_osm_db_with_drn_data(drn_curs: cursor, osm_curs: cursor, osm_conn: connection):
    def copy_table(table_name: str):
        osm_curs.execute(f"CREATE TABLE drn_{table_name} AS SELECT * FROM {table_name} WHERE 1=0;")
        osm_conn.commit()

        drn_curs.execute(f"select * from {table_name}")
        drn_ways = drn_curs.fetchall()

        logger.info(f"moving data from drn db to osm db, inserting {len(drn_ways)} rows")
        for values in drn_ways:
            placeholder_query = f"INSERT INTO drn_{table_name} VALUES ({', '.join('%s' for _ in range(len(values)))})"
            query = osm_curs.mogrify(placeholder_query, tuple(values))
            osm_curs.execute(query)
        osm_conn.commit()

    copy_table("planet_osm_line")
    copy_table("planet_osm_point")


def setup_db():
    create_db("drn")
    create_db("osm")

    # --- import drn ---
    # make sure osm file is properly ordered since import will fail otherwise
    # import osm file to created database

    # subprocess.run([f'osmium sort {TRANSFORMED_DRN_FILEPATH} -o {DRN_TMP_FILE_PATH}'], shell=True)
    subprocess.run([f'cp {TRANSFORMED_DRN_FILEPATH} {DRN_TMP_FILE_PATH}'], shell=True)
    # prevent that osm2psql throws way nodes simply away when importing
    logger.info(f"Insert node tags to prevent removal during importing")
    insert_node_tag(DRN_TMP_FILE_PATH)
    subprocess.run([f'osm2pgsql {osm_2_psql_host_param} -d "drn" --hstore --hstore-add-index {DRN_TMP_FILE_PATH}'], shell=True)
    subprocess.run([f'rm "{DRN_TMP_FILE_PATH}"'], shell=True)

    # --- import osm ---
    subprocess.run([f'osm2pgsql {osm_2_psql_host_param} -d "osm" --hstore --hstore-add-index {OSM_FILE_PATH}'], shell=True)


def create_db(db_name: str):
    # create database and activate extensions for postgis
    p = subprocess.run([f'createdb -U {psql_user} {psql_host_param} {db_name}'], shell=True)
    if p.returncode != 0:
        raise Exception(f"Could not create database {db_name}")
    p = subprocess.run([f'psql {psql_host_param} {db_name} -c "CREATE EXTENSION postgis;"'], shell=True)
    if p.returncode != 0:
        raise Exception(f"Could not activate postgis extension for database {db_name}")
    p = subprocess.run([f'psql {psql_host_param} {db_name} -c "CREATE EXTENSION hstore;"'], shell=True)
    if p.returncode != 0:
        raise Exception(f"Could not activate hstore extension for database {db_name}")


def open_connection(db_name: str):
    if psql_host and psql_user and psql_pass:
        conn = psycopg2.connect(database=db_name, host=psql_host, user=psql_user, password=psql_pass)
    else:
        conn = psycopg2.connect(database=db_name)
    curs = conn.cursor()
    return conn, curs


def update_projection(curs: cursor, conn: connection, table_name: str, geometry_type: str):
    """
    update the epsg used in order to allow distance calculations
    original data is kept, but a new column with data in a preferable epsg is created beside it
    """

    # create a new column containing way geometries in a projection where distances can be meassured (1 unit ~ 1 meter)
    curs.execute(f"""ALTER TABLE {table_name} ADD COLUMN way_32633 geometry({geometry_type},32633);""")
    curs.execute(f"""UPDATE {table_name} SET way_32633 = ST_Transform(way, 32633);""")
    conn.commit()


def ways_close_to_border(curs: cursor, table_name: str, max_distance: int):
    project = partial(pyproj.transform, pyproj.Proj('EPSG:4326'), pyproj.Proj('EPSG:32633'), always_xy=True)
    hamburg_boundary_line = LineString(get_boundary_hamburg())
    hamburg_boundary_line_projected = transform(project, hamburg_boundary_line)
    linestring_string = str(hamburg_boundary_line_projected)

    curs.execute("""SELECT osm_id 
        from %s 
        where highway is not null 
        and st_dwithin(way_32633, 'SRID=32633;%s'::geometry, %s);""" % (table_name, linestring_string, max_distance))
    ways = curs.fetchall()
    return ways


def boundary_line_as_32633():
    project = partial(pyproj.transform, pyproj.Proj('EPSG:4326'), pyproj.Proj('EPSG:32633'), always_xy=True)
    hamburg_boundary_line = LineString(get_boundary_hamburg())
    hamburg_boundary_line_projected = transform(project, hamburg_boundary_line)
    return hamburg_boundary_line_projected


def nodes_close_to_border(curs: cursor, table_name: str, max_distance: int):
    """
    given a :table_name search and return all geometries in this table having a maximum distance
    of :max_distance to the city boundary of hamburg
    """
    hamburg_boundary_line_projected = boundary_line_as_32633()
    linestring_string = str(hamburg_boundary_line_projected)

    curs.execute("""SELECT osm_id from %s where st_dwithin(way_32633, 'SRID=32633;%s'::geometry, %s);""" % (
        table_name, linestring_string, max_distance))
    nodes = curs.fetchall()
    return nodes


if __name__ == '__main__':
    find_matches()
