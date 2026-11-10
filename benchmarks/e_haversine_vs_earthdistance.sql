-- earthdistance <-> (GiST index) vs haversine (no index possible)
EXPLAIN ANALYZE SELECT id_ride FROM ride
ORDER BY ll_to_earth(pickup_latitude, pickup_longitude) <-> ll_to_earth(14.5547, 121.0244)
LIMIT 10;

EXPLAIN ANALYZE SELECT id_ride FROM ride
ORDER BY 2 * 6371000 * asin(sqrt(
    sin(radians(pickup_latitude - 14.5547) / 2) ^ 2
    + cos(radians(14.5547)) * cos(radians(pickup_latitude))
    * sin(radians(pickup_longitude - 121.0244) / 2) ^ 2
))
LIMIT 10;

-- 0 means both rank the 1000 nearest rides in the same order
WITH ed AS (
    SELECT id_ride, row_number() OVER (ORDER BY d, id_ride) AS pos FROM (
        SELECT id_ride, ll_to_earth(pickup_latitude, pickup_longitude) <-> ll_to_earth(14.5547, 121.0244) AS d
        FROM ride ORDER BY d LIMIT 1000
    ) s
),
hv AS (
    SELECT id_ride, row_number() OVER (ORDER BY d, id_ride) AS pos FROM (
        SELECT id_ride, asin(sqrt(
            sin(radians(pickup_latitude - 14.5547) / 2) ^ 2
            + cos(radians(14.5547)) * cos(radians(pickup_latitude))
            * sin(radians(pickup_longitude - 121.0244) / 2) ^ 2
        )) AS d
        FROM ride ORDER BY d LIMIT 1000
    ) s
)
SELECT count(*) FILTER (WHERE ed.pos IS DISTINCT FROM hv.pos) AS different_positions
FROM ed FULL JOIN hv USING (id_ride);
