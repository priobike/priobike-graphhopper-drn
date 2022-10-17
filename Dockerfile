FROM openjdk:8

WORKDIR /graphhopper

COPY . .

# Use this argument to invalidate the cache of subsequent steps.
ARG CACHE_DATE=1970-01-01

RUN wget https://github.com/graphhopper/graphhopper/releases/download/5.3/graphhopper-web-5.3.jar
RUN ./preheat.sh 

ENTRYPOINT ./run.sh
