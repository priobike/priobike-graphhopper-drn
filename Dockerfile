ARG BUILDER_IMAGE=postgis/postgis:14-3.3
# For faster builds on ARM, use --build-arg BUILDER_IMAGE="ghcr.io/baosystems/postgis:14-3.3"
FROM $BUILDER_IMAGE as builder
# This docker image is based on the bullseye operating system
# See: https://github.com/postgis/docker-postgis/blob/master/14-3.3/Dockerfile

ENV POSTGRES_NAME=db
ENV POSTGRES_USER=db
ENV POSTGRES_PASSWORD=db
ENV POSTGRES_DB=db
ENV POSTGRES_HOST=localhost
ENV POSTGRES_PORT=5432

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gdal-bin libgdal-dev g++ osmium-tool make cmake \
    libboost-dev libboost-system-dev libboost-filesystem-dev \
    libexpat1-dev zlib1g-dev libbz2-dev libpq-dev libproj-dev \
    lua5.3 liblua5.3-dev pandoc postgresql postgresql-contrib \
    nlohmann-json3-dev pyosmium \
    python3 python3-pip python3-venv

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV DRN_FILEPATH="./resources/drn.gml"

RUN pip install poetry
COPY ./converter/pyproject.toml .
RUN poetry install

RUN mkdir conflation
RUN mkdir resources

# Build from source since the version is important.
RUN apt-get install -y git
RUN git clone https://github.com/openstreetmap/osm2pgsql.git
RUN cd osm2pgsql && mkdir build && cd build && cmake .. && make && make install && cd ../..

# Use this argument to invalidate the cache of subsequent steps.
ARG CACHE_DATE=1970-01-01

# See: https://www.govdata.de/suchen/-/details/radverkehrsnetz-hamburg
RUN apt-get install -y wget
RUN wget -O resources/drn.gml "https://geodienste.hamburg.de/HH_WFS_Radverkehrsnetz?SERVICE=WFS&VERSION=1.1.0&REQUEST=GetFeature&typename=de.hh.up:radwege_fahrradstrasse,de.hh.up:radwege_gruenflaechen,de.hh.up:radwege_mischverkehr,de.hh.up:radwege_radweg,de.hh.up:radwege_schiebestrecke,de.hh.up:radwege_sonstige,de.hh.up:radwege_streifen"
RUN sed -i 's/ �//g' resources/drn.gml
RUN wget -O resources/hamburg-latest.osm.bz2 https://download.geofabrik.de/europe/germany/hamburg-latest.osm.bz2
RUN bzip2 -d resources/hamburg-latest.osm.bz2

# Install Postgres client to check liveness of the database.
RUN apt-get install -y postgresql-client

# Run the actual conversion process.
COPY ./converter .
RUN chmod +x convert.sh
RUN ./convert.sh

FROM openjdk:8 AS runner

# Use this argument to invalidate the cache of subsequent steps. Need to be put here again because of the multi-stage build.
ARG CACHE_DATE=1970-01-01

WORKDIR /graphhopper

RUN wget https://github.com/graphhopper/graphhopper/releases/download/5.3/graphhopper-web-5.3.jar

COPY preheat.sh .
COPY run.sh .
COPY config-bike.yml .

COPY --from=builder /app/resources/osm_with_drn_conflated.osm map.osm

RUN ./preheat.sh 

HEALTHCHECK --interval=5s --timeout=3s CMD curl --fail http://localhost:8989/health || exit 1

ENTRYPOINT ./run.sh
