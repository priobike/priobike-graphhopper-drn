import json
import subprocess

""" using paths based on drn and osm routes request matched connections by sg-selector and format the results"""


def sg_match_paths():
    path_file_names = ["route_4_drn.json_sg", "route_4_osm.json_sg",
                       "route_5_drn.json_sg", "route_5_osm.json_sg",
                       "route_6_drn.json_sg", "route_6_osm.json_sg",
                       "route_7_drn.json_sg", "route_7_osm.json_sg"
                       ]

    for file_name in path_file_names:
        match_file_name = f"./testroutes/random_routes/matched_{file_name[:-3]}"
        subprocess.run([f'curl --data "@testroutes/random_routes/{file_name}" https://priobike.vkw.tu-dresden.de/production/sg-selector-backend/routing/select > {match_file_name}'],
                       shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        with open(match_file_name) as f:
            match = json.load(f)

        signal_group_ids = [ele['signalGroupId'] for ele in match['route']]

        deduplicated_signal_group_ids = [signal_group_ids[0]]
        for idx in range(1, len(signal_group_ids)):
            if signal_group_ids[idx] != signal_group_ids[idx - 1]:
                deduplicated_signal_group_ids.append(signal_group_ids[idx])

        print(f"{file_name} has matched signal groups: {deduplicated_signal_group_ids}")


if __name__ == '__main__':
    sg_match_paths()
