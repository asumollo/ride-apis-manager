-- ?status=pickup&ordering=pickup_time: ride_status_pickup_time_idx
BEGIN;

-- 1. with the status index
EXPLAIN ANALYZE SELECT * FROM ride WHERE status = 'pickup' ORDER BY pickup_time, id_ride LIMIT 10;

DROP INDEX IF EXISTS ride_status_pickup_time_idx;

-- 2. falls back to the pickup-time index
EXPLAIN ANALYZE SELECT * FROM ride WHERE status = 'pickup' ORDER BY pickup_time, id_ride LIMIT 10;

-- 3. deep page: the fallback has to skip far more rows
EXPLAIN ANALYZE SELECT * FROM ride WHERE status = 'pickup' ORDER BY pickup_time, id_ride LIMIT 10 OFFSET 50000;

DROP INDEX IF EXISTS ride_pickup_time_idx;

-- 4. no index at all
EXPLAIN ANALYZE SELECT * FROM ride WHERE status = 'pickup' ORDER BY pickup_time, id_ride LIMIT 10;

ROLLBACK;

-- 5. same deep page with the status index, for comparison with 3
EXPLAIN ANALYZE SELECT * FROM ride WHERE status = 'pickup' ORDER BY pickup_time, id_ride LIMIT 10 OFFSET 50000;

-- in case auto-commit kept the DROP
CREATE INDEX IF NOT EXISTS ride_status_pickup_time_idx ON ride (status, pickup_time, id_ride);
CREATE INDEX IF NOT EXISTS ride_pickup_time_idx ON ride (pickup_time, id_ride);
