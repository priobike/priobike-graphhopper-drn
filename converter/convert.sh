#!/bin/bash

# Run postgres in the background
echo "Starting postgres..."
/usr/local/bin/docker-entrypoint.sh postgres \
  -c log_destination=stderr \
  -c max_parallel_workers_per_gather=4 \
  &
pid=$!
echo "Postgres started with pid $pid"

echo "Waiting for postgres server..."
# Await PostGreSQL server to become available
RETRIES=20
while [ "$RETRIES" -gt 0 ]
do
  PG_STATUS="$(pg_isready -d ${POSTGRES_NAME} -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER})"
  PG_EXIT=$(echo $?)
  if [ "$PG_EXIT" = "0" ];
    then
      RETRIES=0
  fi
  sleep 0.5
done
echo "Postgres server is up!"

echo "Transforming DRN into OSM..."
python3 drn_transform.py

# FIXME: We currently use the non-conflated data, since the build
# runs out of memory on the CI server.
# echo "Preparing OSM dataset outside of Hamburg..."
# python3 osm_extract.py
# echo "Find matches between DRN nodes and OSM nodes..."
# python3 postgis_connector.py
# echo "Conflating OSM and DRN..."
# python3 map_conflation.py
