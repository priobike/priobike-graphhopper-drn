import logging

from drn_transform import transform_drn_to_osm
from map_conflation import conflate
from osm_extract import extract_region_outside_hh, cut_osm_ways_after_border
from postgis_connector import find_matches

""" 
script to start from a original DRN Dataset and go through all steps necessary to create a dataset allowing routing
inside hamburg with drn routes and fallback to osm data should routes cross the city border

Depending on the used dataset sizes this takes several minutes, and will create intermediate datasets during the
process.
"""

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


def main():
    logger.info("Step 1: Transform DRN to OSM")
    transform_drn_to_osm()

    logger.info("Step 2: Extract region outside Hamburg")
    extract_region_outside_hh()
    logger.info("Step 3: Cut OSM ways after border")
    cut_osm_ways_after_border()

    logger.info("Step 4: Find matches")
    find_matches()
    logger.info("Step 5: Conflate")
    conflate()


if __name__ == '__main__':
    main()
