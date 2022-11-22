

""" Measure snapping distances from requested route start and destination to snapped start and destination """
import random

import requests

from utils import haversine


def measure():
    def get_route_dist(start_coord, dest_coord, url):
        route = requests.get(url).json()
        if 'paths' not in route:
            return -1, -1
        route_start = route['paths'][0]['points']['coordinates'][0]
        route_destination = route['paths'][0]['points']['coordinates'][-1]

        dist_start = haversine(start_coord[1], start_coord[0], route_start[0], route_start[1]) * 1000
        dist_dest = haversine(dest_coord[1], dest_coord[0], route_destination[0], route_destination[1]) * 1000
        return dist_start, dist_dest

    route_count = 10_000

    total_dist_drn = 0
    total_dist_osm = 0

    for i in range(route_count):

        start_coord = get_random_coord_in_hh()
        dest_coord = get_random_coord_in_hh()

        url_drn = f"http://localhost:8989/route?point={start_coord[0]},{start_coord[1]}&point={dest_coord[0]},{dest_coord[1]}&profile=bike_short_fastest&ch.disable=true&locale=de&calc_points=true&instructions=false&points_encoded=false"
        dist_start_drn, dist_dest_drn = get_route_dist(start_coord, dest_coord, url_drn)


        url_osm = f"http://localhost:8995/route?point={start_coord[0]},{start_coord[1]}&point={dest_coord[0]},{dest_coord[1]}&profile=bike_short_fastest&ch.disable=true&locale=de&calc_points=true&instructions=false&points_encoded=false"
        dist_start_osm, dist_dest_osm = get_route_dist(start_coord, dest_coord, url_osm)

        if dist_start_drn == -1 or dist_start_osm == -1:
            continue

        total_dist_drn += dist_start_drn + dist_dest_drn
        total_dist_osm += dist_start_osm + dist_dest_osm

    print(f"Average dist drn: {total_dist_drn / (route_count * 2)}")
    print(f"Average dist osm: {total_dist_osm / (route_count * 2)}")


def get_random_coord_in_hh():
    return round(random.uniform(53.5, 53.64), 4), round(random.uniform(9.88, 10.1), 4)


if __name__ == '__main__':
    measure()
