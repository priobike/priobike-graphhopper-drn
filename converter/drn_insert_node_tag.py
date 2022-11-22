from lxml import etree


def insert_node_tag(osm_file_path):
    """
    given an osm file path open it and set on each node a name tag if not done yet
    this is done because osm2psql would ignore nodes that only specify a location
    without additional information
    """

    osm_xml_data = etree.parse(osm_file_path)

    root = osm_xml_data.getroot()
    for node_element in root.iterchildren(tag="node"):
        etree.SubElement(node_element, "tag", k="name", v="way_node")

    tree = root.getroottree()
    tree.write(osm_file_path, encoding='utf-8', xml_declaration=True, pretty_print=True)


if __name__ == '__main__':
    insert_node_tag("./resources/drn_as_osm.osm")
