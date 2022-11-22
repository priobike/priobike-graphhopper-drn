import math

import osmium
from osmium.osm._osm import TagList, Way, Relation

"""
standalone script which reads a .osm file and generates some metrics
as total edge count, bicycle line lengths, etc.
"""

OSM_FILE_PATH = "./resources/hamburg-latest_2022_05_16.osm"
DRN_FILE_PATH = "./resources/drn_without_exclave.osm"

# A global factory that creates WKB from an osmium geometry
# wkbfab = osmium.geom.WKBFactory()


def main():
    print("---- Statistics for Hamburg from OSM Sources ----")
    generate_statistics(OSM_FILE_PATH)

    print("---- Statistics for Hamburg from DRN Sources ----")
    generate_statistics(DRN_FILE_PATH)


def generate_statistics(file_path):
    h = CounterHandler()

    h.apply_file(file_path, locations=True)

    print(f"#### Metrics of file {file_path} ####")
    print(f"Number of nodes:        {h.num_nodes}")
    print(f"Number of ways:         {h.num_ways}")

    print(f"Total way length:       {round(h.total_length / 1000, 2)} km")
    print(f"Average segment length: {round(h.total_length / h.num_ways, 2)}m")
    print(f"Total width length:     {round(h.total_length_width / 1000, 2)} km")
    print(f"Widths: {h.total_length_width_multi}")
    print(f"Total surface length:   {round(h.total_length_surface / 1000, 2)} km")
    print(f"Total grade length:   {round(h.total_length_tracktype / 1000, 2)} km")

    total_bicycle_routes_length = 0
    for relation_id, members in h.relation_way_member_ids.items():
        length = 0
        for member_id in members:
            if member_id not in h.way_lengths:
                continue
            length += h.way_lengths[member_id]
        total_bicycle_routes_length += length

    print(f"Total official bicycle route length: {round(total_bicycle_routes_length / 1000, 2)} km")


class CounterHandler(osmium.SimpleHandler):
    def __init__(self):
        osmium.SimpleHandler.__init__(self)
        self.num_nodes = 0
        self.num_ways = 0
        self.total_length = 0
        self.total_length_width = 0
        self.total_length_width_multi = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, -1: 0}
        self.num_ways_with_width = 0
        self.total_length_surface = 0
        self.total_length_tracktype = 0
        self.total_length_official_routes = 0
        self.way_lengths = dict()
        self.relation_way_member_ids = dict()

    def meassure_way_length(self, way: Way):
        try:
            dist = osmium.geom.haversine_distance(way.nodes)
            self.way_lengths[way.id] = dist
            return dist
        except osmium.InvalidLocationError:
            # A location error might occur if the osm file is an extract
            # where nodes of ways near the boundary are missing.
            print("WARNING: way %d incomplete. Ignoring." % way.id)
            return 0

    def node(self, tags: TagList):
        self.num_nodes += 1

    def way(self, way: Way):
        if 'highway' not in way.tags \
                or way.tags.get('highway') in ['motorway', 'motorway_link', 'trunk_link'] \
                or way.tags.get('access') == 'private' \
                or (way.tags.get('highway') == 'footway' and way.tags.get('bicycle') != 'yes') \
                or way.tags.get('bicycle') == 'no':
            return

        length = self.meassure_way_length(way)
        self.num_ways += 1
        self.total_length += length
        available_widths = [width_val_to_float(way.tags.get(tag)) for tag in ['width', 'cycleway:right:width', 'cycleway:width', 'cycleway:both:width'] if tag in way.tags]
        if any(available_widths):
            self.num_ways_with_width += 1
            self.total_length_width += length
            rounded_width = math.ceil(min(available_widths))
            if rounded_width <= 5:
                self.total_length_width_multi[rounded_width] += length
            else:
                self.total_length_width_multi[-1] += length
        if any([True if tag in way.tags else False for tag in ['surface', 'cycleway:surface', 'cycleway:right:surface', 'cycleway:left:surface', 'cycleway:both:surface']]):
            self.total_length_surface += length
        if 'tracktype' in way.tags:
            self.total_length_tracktype += length

    def relation(self, relation: Relation):
        if relation.tags.get('type') == 'route' and relation.tags.get('route') == 'bicycle':
            members = relation.members
            self.relation_way_member_ids[relation.id] = []
            for member in members:
                if member.type == 'w':
                    self.relation_way_member_ids[relation.id].append(member.ref)


def width_val_to_float(width_str: str):
    """ sanitize a given string and convert it to a float containing a width in meter"""
    if "cm" in width_str:
        width_str = width_str.replace("cm", "")
        width = float(width_str) / 100
    elif "m" in width_str:
        width = float(width_str.replace("m", ""))
    else:
        width = float(width_str)
    return width


if __name__ == '__main__':
    main()
