-- Recreates any missing index from these scripts
CREATE INDEX IF NOT EXISTS ride_pickup_time_idx ON ride (pickup_time, id_ride);
CREATE INDEX IF NOT EXISTS ride_status_pickup_time_idx ON ride (status, pickup_time, id_ride);
CREATE INDEX IF NOT EXISTS ride_event_ride_created_idx ON ride_event (id_ride, created_at);
CREATE INDEX IF NOT EXISTS ride_pickup_earth_idx ON ride USING gist (ll_to_earth(pickup_latitude, pickup_longitude));

SELECT indexname FROM pg_indexes WHERE indexname LIKE 'ride_%_idx' ORDER BY 1;
