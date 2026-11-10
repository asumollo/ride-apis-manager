-- The todays_ride_events prefetch for the first page: ride_event_ride_created_idx
BEGIN;

-- with the index
EXPLAIN ANALYZE SELECT * FROM ride_event
WHERE created_at >= now() - interval '24 hours'
  AND id_ride IN (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
ORDER BY created_at DESC;

DROP INDEX IF EXISTS ride_event_ride_created_idx;

-- without the index
EXPLAIN ANALYZE SELECT * FROM ride_event
WHERE created_at >= now() - interval '24 hours'
  AND id_ride IN (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
ORDER BY created_at DESC;

ROLLBACK;

-- in case auto-commit kept the DROP
CREATE INDEX IF NOT EXISTS ride_event_ride_created_idx ON ride_event (id_ride, created_at);
