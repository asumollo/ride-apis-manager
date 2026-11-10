-- ?ordering=pickup_time: ride_pickup_time_idx
BEGIN;

-- with the index
EXPLAIN ANALYZE SELECT * FROM ride ORDER BY pickup_time, id_ride LIMIT 10;

DROP INDEX IF EXISTS ride_pickup_time_idx;

-- without the index
EXPLAIN ANALYZE SELECT * FROM ride ORDER BY pickup_time, id_ride LIMIT 10;

ROLLBACK;

-- in case auto-commit kept the DROP
CREATE INDEX IF NOT EXISTS ride_pickup_time_idx ON ride (pickup_time, id_ride);
