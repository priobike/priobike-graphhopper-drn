import json
import os


def convert(file_name: str, is_geojson: bool):
    with open(file_name) as f:
        route = json.load(f)

    if is_geojson:
        coordinates = route["features"][0]["geometry"]["coordinates"][0]
    else:
        coordinates = route["paths"][0]["points"]["coordinates"]

    request = {
        "route": [{"lon": coord[0], "lat": coord[1], "alt": 0} for coord in coordinates]
    }

    with open(f"{file_name}_sg", "w") as f:
        json.dump(request, f)

    print("sg-selector request:")
    print(request)


if __name__ == '__main__':
    routes_dir = "testroutes/random_routes"
    for filename in os.listdir(routes_dir):
        if filename.startswith("route_") and filename.endswith(".json"):
            file_path = os.path.join(routes_dir, filename)
            convert(file_path, False)
