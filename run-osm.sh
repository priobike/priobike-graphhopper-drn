#!/bin/bash

# Skip the DRN build step
docker build --target osm-dgm-runner -t osm-dgm-runner -f Dockerfile .
docker run --rm -p 8989:8989 --name osm-dgm-runner osm-dgm-runner