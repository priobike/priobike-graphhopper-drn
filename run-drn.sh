#!/bin/bash

# Skip the DRN build step
docker build --target drn-dgm-runner -t drn-dgm-runner -f Dockerfile .
docker run --rm -p 8989:8989 --name drn-dgm-runner drn-dgm-runner