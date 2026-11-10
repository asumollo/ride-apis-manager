-- ?ordering=distance&lat=14.5547&lng=121.0244: ride_pickup_earth_idx (GiST)
BEGIN;

-- with the index
EXPLAIN ANALYZE SELECT id_ride FROM ride
ORDER BY ll_to_earth(pickup_latitude, pickup_longitude) <-> ll_to_earth(14.5547, 121.0244)
LIMIT 10;

DROP INDEX IF EXISTS ride_pickup_earth_idx;

-- without the index
EXPLAIN ANALYZE SELECT id_ride FROM ride
ORDER BY ll_to_earth(pickup_latitude, pickup_longitude) <-> ll_to_earth(14.5547, 121.0244)
LIMIT 10;

ROLLBACK;

-- in case auto-commit kept the DROP
CREATE INDEX IF NOT EXISTS ride_pickup_earth_idx ON ride USING gist (ll_to_earth(pickup_latitude, pickup_longitude));
