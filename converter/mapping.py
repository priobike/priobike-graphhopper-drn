import os
from typing import Dict

from dotenv import load_dotenv
from utils import get_bool_variable

load_dotenv()
ONEWAY_TRAVEL_BY_SETTING_MAX_SPEED = get_bool_variable('ONEWAY_TRAVEL_BY_SETTING_MAX_SPEED')
ENABLE_TRAVELLING_ONEWAY = get_bool_variable('ENABLE_TRAVELLING_ONEWAY')


radweg_art_mapping = {
    "Aufgeweiteter Radaufstellstreifen": {
        "highway": "tertiary"
    },
    # Todo: source node needs: cycleway=asl
    "Busfahrstreifen mit Radverkehr": {
        "cycleway": "share_busway",
        "highway": "service",
    },
    "Fähre": {
        "route": "ferry",
        "bicycle": "yes",
    },
    "Fahrradstraße": {
        "bicycle_road": "yes",
        "bicycle": "designated",
        "maxspeed": "30",
        "source:maxspeed": "DE:bicycle_road",
        "traffic_sign": "DE:244.1",
        "highway": "residential",
    },
    "Fußgängerüberweg/-furt (Schiebestrecke)": {
        "highway": "pedestrian" # todo if "crossing" is used ways get excluded
    },
    "Fußgängerzone - immer befahrbar": {
        "highway": "pedestrian",
        "bicycle": "yes",
    },
    # todo include timespan
    "Fußgängerzone (meist zeitlich begrenzt)": {
        "highway": "pedestrian",
    },
    "Fußgängerzone - zeitlich begrenzt": {
        "highway": "pedestrian",
    },
    "Gehweg (Fahrrad frei)": {
        "highway": "footway",
        "foot": "designated",
        "bicycle": "yes",
        "traffic_sign": "DE:239,1022-10",
    },
    # equal to Gehweg (Fahrrad frei) in meaning
    "Gehweg (nur ZZ 1022-10)": {
        "highway": "footway",
        "foot": "designated",
        "bicycle": "yes",
        "traffic_sign": "DE:239,1022-10",
    },
    "Gehweg (Schiebestrecke)": {
        "highway": "footway",
    },
    "Gemeinsamer Geh-/Radweg": {
        "highway": "path",
        "bicycle": "designated",
        "foot": "designated",
        "segregated": "no",
    },
    "Getrennter Geh-/Radweg": {
        "highway": "path",
        "bicycle": "designated",
        "foot": "designated",
        "segregated": "yes",
    },
    "Kommunaltrasse": {
        "cycleway": "share_busway",
        "highway": "tertiary",
    },
    "Kopenhagener Radweg": {
        "highway": "cycleway",
        "bicycle": "designated"
    },
    "Protected Bike Lane": {
        "highway": "cycleway",
        "bicycle": "designated"
    },
    "Radfahrstreifen": {
        "highway": "tertiary",
        "cycleway:right": "lane",
        "cycleway:right:bicycle": "designated",
    },
    "Radweg (mit Grünstreifen vom Gehweg getrennt)": {
        "highway": "path",
        "bicycle": "designated",
        "foot": "designated",
        "segregated": "yes",
    },
    "Schutzstreifen": {
        "highway": "tertiary",
        "cycleway:right": "lane",
        "cycleway:lane": "advisory",  # both options possible
        "cycleway:protection:right": "dashed_line",
    },
    "Straße mit Mischverkehr ab 50 km/h": {
        "highway": "tertiary",
        "bicycle": "yes",
    },
    "Straße mit Mischverkehr bis 30 km/h": {
        "highway": "residential",
        "bicycle": "yes",
    },
    "Verkehrsberuhigter Bereich / Befahrbarer Wohnweg": {
        "highway": "living_street",
        "bicycle": "yes",
    },
    "Verkehrsberuhigter Geschäftsbereich": {
        "highway": "living_street",
        "bicycle": "yes",
    },
    "Wege in Grünflächen": {
        "highway": "path",
        "bicycle": "yes",
    },
    "Wirtschaftsweg": {
        "highway": "track",
        "bicycle": "yes",
    },
}

oberflaeche_mapping = {
    # Todo: Node should get tag "railway=level_crossing"
    "Bahnübergang": {},
    "befestigt - nicht genauer erkennbar": {
        "surface": "compacted",
    },
    "befestigt - zu detailieren": {
        "surface": "compacted",
    },
    "Betonplatten": {
        "surface": "concrete:plates",
    },
    "Bituminöse Decke": {
        "surface": "asphalt",
    },
    "Holz": {
        "surface": "wood",
    },
    "Kunststein-Pflaster": {
        "surface": "paving_stones",
    },
    "Metall": {
        "surface": "metal",
    },
    "Naturstein-Pflaster": {
        "surface": "cobblestone"
    },
    # Todo order is important what happens if it's a foot path?
    "Treppe": {
        "highway": "steps",
    },
    "unbefestigt": {
        "surface": "unpaved",
    },
    "Wassergebundene Decke": {
        "surface": "compacted"
    },
}

fahrradroute_mapping = {
    "type": "route",
    "route": "bicycle",
    "network": "lcn",
}

niveau_mapping = {
    "bodengleich": {},  # no handling required
    "Brücke": {
        "bridge": "yes",
    },
    "Tunnel": {
        "tunnel": "yes",
    }
}


def radweg_art_to_osm_tags(radweg_art: str) -> Dict:
    if radweg_art not in radweg_art_mapping:
        raise ValueError(f"Received an unexpected value for radweg_art '{radweg_art}' consider adding it to the mapping")
    return radweg_art_mapping[radweg_art]


def oberflaeche_to_osm_tags(oberflaeche: str) -> Dict:
    if oberflaeche not in oberflaeche_mapping:
        raise ValueError(f"Received an unexpected value for oberflaeche '{oberflaeche}' consider adding it to the mapping")
    return oberflaeche_mapping[oberflaeche]


def niveau_to_osm_tags(niveau: str) -> Dict:
    if niveau not in niveau_mapping:
        raise ValueError(f"Received an unexpected value for niveau '{niveau}' consider adding it to the mapping")
    return niveau_mapping[niveau]


def richtung_to_osm_tags(richtung: str) -> Dict:
    if richtung == "in Geometrie-Richtung":
        if ONEWAY_TRAVEL_BY_SETTING_MAX_SPEED and ENABLE_TRAVELLING_ONEWAY:
            # if a backward speed is supplied GraphHopper uses min(maxspeed, maxspeed:backward) as speed for both
            # directions, from my understanding that's not a good evaluation see #2662 on graphhopper for possible
            # feedback
            return {"maxspeed:backward": "5"}
        else:
            return {"oneway": "yes"}
    if richtung == "in beide Richtungen":
            return {"oneway": "no"}
    raise ValueError(f"Unknown value for attribute 'richtung', was: {richtung}")
