import json
import os
from math import asin, cos, radians, sin, sqrt
from typing import List

from dotenv import load_dotenv

load_dotenv()


def get_boundary_hamburg() -> List[List[float]]:
    """ load a boundary coordinate list of hamburgs city outline """
    with open("resources/hamburg_boundary.geojson") as f:
        hamburg_boundary = json.load(f)
    print("Loaded boundary of Hamburg")
    return hamburg_boundary['geometries'][0]['coordinates'][0][0]


def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in kilometers between two points
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles. Determines return value units.
    return c * r


def get_bool_variable(name: str, default_value = None) -> bool:
    true_ = ('True', 'true', '1', 't')  # Add more entries if you want, like: `y`, `yes`, ...
    false_ = ('False', 'false', '0', 'f')
    value = os.getenv(name, None)
    if value is None:
        if default_value is None:
            raise ValueError(f'Variable `{name}` not set!')
        else:
            value = str(default_value)
    if value.lower() not in true_ + false_:
        raise ValueError(f'Invalid value `{value}` for variable `{name}`')
    return value in true_


def get_psql_host_param():
    psql_host = os.getenv("POSTGRES_HOST")
    psql_user = os.getenv("POSTGRES_USER")
    if psql_host and psql_user:
        return f"-h {psql_host} -U {psql_user}"
    else:
        return ""


def get_osm_2_psql_host_param():
    psql_host = os.getenv("POSTGRES_HOST")
    psql_user = os.getenv("POSTGRES_USER")
    if psql_host and psql_user:
        return f"-H {psql_host} -U {psql_user}"
    else:
        return ""
