-- Trips longer than 1 hour from pickup to dropoff, by month and driver
WITH trips AS (
    SELECT
        id_ride,
        MIN(created_at) FILTER (WHERE description = 'Status changed to pickup') AS pickup_at,
        MAX(created_at) FILTER (WHERE description = 'Status changed to dropoff') AS dropoff_at
    FROM ride_event
    WHERE description IN ('Status changed to pickup', 'Status changed to dropoff')
    GROUP BY id_ride
)
SELECT
    to_char(trips.pickup_at, 'YYYY-MM') AS "Month",
    users.first_name || ' ' || left(users.last_name, 1) AS "Driver",
    count(*) AS "Count of Trips > 1 hr"
FROM trips
JOIN ride ON ride.id_ride = trips.id_ride
JOIN users ON users.id_user = ride.id_driver
WHERE trips.dropoff_at - trips.pickup_at > interval '1 hour'
GROUP BY "Month", users.id_user, "Driver"
ORDER BY "Month", "Driver";
