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

echo "Running drn_transform.py..."
python3 drn_transform.py
echo "Running osm_extract.py..."
python3 osm_extract.py
echo "Running postgis_connector.py..."
python3 postgis_connector.py
echo "Running map_conflation.py..."
python3 map_conflation.py
