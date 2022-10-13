#!/bin/bash

# Normally, the docker container will need to process data when it is started.
# This will cause a lot of time and redundant comutational effort to be wasted.
# So, we can preheat the docker images to avoid this problem. This script is 
# part of the Dockerfile, and will be executed when the docker image is built.

echo "Preheating the docker image..."

# Run GraphHopper in the background.
./run.sh &

# Use CURL to wait for the server to start.
while ! curl -s localhost:8989; do sleep 1; done

# Stop the server.
kill $(ps aux | grep '[j]ava' | awk '{print $2}')

# The server is now ready to be used.
echo "GraphHopper is ready to be used."
