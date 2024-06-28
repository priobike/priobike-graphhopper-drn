FROM maven as dgm-builder
WORKDIR /app
# Clone graphhopper 8.0 from https://github.com/graphhopper/graphhopper
RUN git clone --branch 9.1 --depth 1 https://github.com/graphhopper/graphhopper
WORKDIR /app/graphhopper
# Inject our custom DGM code
COPY ./graphhopper .
# Build
RUN mvn -B package -DskipTests=true
# Make sure the jar is available in the next stage
RUN cp web/target/graphhopper-web-*.jar /app/graphhopper-web.jar

FROM postgis/postgis:14-3.3 as drn-builder
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

FROM openjdk:17 AS osm-dgm-runner
WORKDIR /graphhopper
# Get the jar from the first build stage
COPY --from=dgm-builder /app/graphhopper/web/target/graphhopper-web-*.jar graphhopper-web.jar
COPY config-bike.yml .
ARG CACHE_DATE=1970-01-01
RUN wget http://download.geofabrik.de/europe/germany/hamburg-latest.osm.pbf
HEALTHCHECK --interval=5s --timeout=3s CMD curl --fail http://localhost:8989/health || exit 1
ENTRYPOINT java -Ddw.server.application_connectors[0].bind_host=0.0.0.0 \
    -Ddw.server.application_connectors[0].port=8989 \
    -Ddw.graphhopper.datareader.file=./hamburg-latest.osm.pbf \
    -jar /graphhopper/*.jar \
    server \
    /graphhopper/config-bike.yml

FROM openjdk:17 AS drn-dgm-runner
WORKDIR /graphhopper
# Get the jar from the first build stage
COPY --from=dgm-builder /app/graphhopper/web/target/graphhopper-web-*.jar graphhopper-web.jar
COPY preheat.sh .
COPY config-bike.yml .
COPY --from=drn-builder /app/resources/osm_with_drn_conflated.osm map.osm
RUN ./preheat.sh 
HEALTHCHECK --interval=5s --timeout=3s CMD curl --fail http://localhost:8989/health || exit 1
ENTRYPOINT java -Ddw.server.application_connectors[0].bind_host=0.0.0.0 \
    -Ddw.server.application_connectors[0].port=8989 \
    -Ddw.graphhopper.datareader.file=./map.osm \
    -jar /graphhopper/*.jar \
    server \
    /graphhopper/config-bike.yml