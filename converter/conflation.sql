
-- add a new column with the correct projection
ALTER TABLE planet_osm_line ADD COLUMN way_32633 geometry(LineString,32633);
--- fill new column with data
UPDATE planet_osm_line SET way_32633 = ST_Transform(way, 32633);


/* get coordinate projection for column */
select Find_SRID('public', 'planet_osm_line', 'way');

/* find ways in distance to a fix point */
select *
from planet_osm_roads
where st_dwithin(way_new, st_point(155518.11320647865, 5952595.21647362, 32633)::geometry, 600);

-- 1102952.1, 7105778.5
select *, st_distance(way_32633, st_point(155518.11320647865, 5952595.21647362, 32633)::geometry)
from planet_osm_line
where st_dwithin(way_32633, st_point(155518.11320647865, 5952595.21647362, 32633)::geometry, 6);

select * from planet_osm_line limit 5;

select ol.osm_id, st_distance(dl.way_32633, ol.way_32633) as distance from planet_osm_line as ol cross join drn_planet_osm_line as dl where dl.osm_id = 10003678 and ol.highway is not null order by distance asc;

select st_asgeojson(ST_Transform(way_32633, 4326)) from drn_planet_osm_line where osm_id = 10003678;
select st_asgeojson(st_transform(way_32633, 4326)) from drn_planet_osm_line where osm_id = 10003678;

-- 155518.11320647865, 5952595.21647362
CREATE TABLE drn_border_points
(
    osm_id   int PRIMARY KEY,
    location geometry(POINT, 4326)
);

create table hamburg_bounding_polygon
(
    id int PRIMARY KEY,
    geom geometry(LINESTRING, 32633)
);

select * from planet_osm_line limit 10