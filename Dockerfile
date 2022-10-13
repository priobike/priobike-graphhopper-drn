FROM openjdk:8

WORKDIR /graphhopper

COPY . .

RUN wget https://github.com/graphhopper/graphhopper/releases/download/5.3/graphhopper-web-5.3.jar
RUN ./preheat.sh 

ENTRYPOINT ./run.sh
