#!/bin/bash

java -Ddw.server.application_connectors[0].bind_host=0.0.0.0 \
    -Ddw.server.application_connectors[0].port=8989 \
    -Ddw.graphhopper.datareader.file=./drn_as_osm.osm \
    -jar /graphhopper/*.jar \
    server \
    /graphhopper/config-bike.yml