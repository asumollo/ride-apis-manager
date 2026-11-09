# Ride APIs

A Django REST Framework API for managing rides, their riders and drivers, and ride events. Only users with the `admin` role can use it.

Built with Django 6.1, Django REST Framework 3.18, PostgreSQL 16 and Python 3.13.

## Quick start

You need Docker.

```bash
git clone https://github.com/asumollo/ride-apis-manager.git
cd ride-apis-manager
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed
```

`seed` adds sample data and an admin user (`admin` / `admin12345`), then prints the admin's API token:

```bash
curl -H "Authorization: Token <token>" http://localhost:8000/api/rides/
```

Or log in at http://localhost:8000/api-auth/login/ to browse the API.

Run the tests:

```bash
docker compose exec web python manage.py test
```

### Without Docker

You need Python 3.13 and PostgreSQL 16. The database user must be a superuser to add the `earthdistance` extension.

```bash
createuser --superuser --pwprompt rides    # password: rides
createdb --owner rides rides
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed
python manage.py runserver
```

### Seed options

`seed` is for local testing only. It makes fake users and rides, so don't run it against a real database.

| Option | Default | What it does |
|---|---|---|
| `--rides` | 200 | Number of rides to create |
| `--riders` | 50 | Number of riders |
| `--drivers` | 10 | Number of drivers |
| `--days` | 90 | Spread pickup times over the past N days |
| `--admin-password` | `admin12345` | The admin user's password |
| `--reset` | off | Delete all rides and events first |

About 15% of rides are from the last 24 hours, so `todays_ride_events` has data.

## Using the API

Send the token as `Authorization: Token <token>`. There are three endpoints, each with list, create, retrieve, update and delete: `/api/users/`, `/api/rides/` and `/api/ride-events/`.

### Ride list

Each ride includes its rider, its driver and `todays_ride_events`, its events from the last 24 hours.

| Request | What it does |
|---|---|
| `/api/rides/?status=pickup` | Filter by `en-route`, `pickup` or `dropoff` |
| `/api/rides/?rider_email=rider001@example.com` | Filter by the rider's exact email |
| `/api/rides/?id_rider=5` | Filter by rider id |
| `/api/rides/?ordering=pickup_time` or `-pickup_time` | Sort by pickup time |
| `/api/rides/?ordering=distance&lat=14.5995&lng=120.9842` | Sort by nearest pickup |
| `/api/rides/?page=2&page_size=50` | 10 per page by default, up to 100 |

### Errors

Every error is a JSON response.

| Code | When |
|---|---|
| 400 | Invalid fields, the driver is also the rider, an unknown query parameter or ordering, malformed JSON |
| 401 | Missing or invalid token |
| 403 | The user doesn't have the `admin` role |
| 404 | Unknown id or page |
| 409 | Deleting a user who is on a ride |
| 500 | Unexpected error, which is also logged |
| 503 | The database is unavailable |

## Performance

Measured on 500,000 rides. [PR #3](https://github.com/asumollo/ride-apis-manager/pull/3) has the full numbers.

| Optimisation | Before | After |
|---|---|---|
| `select_related` + `Prefetch`, page of 100 rides | 302 queries | 3 queries |
| Index for sorting by pickup time | 34.5 ms | 0.11 ms |
| Index for the status filter with sorting | 29-42 ms | 0.68 ms |
| Index for today's events | 74.3 ms | 0.14 ms |
| GiST index for the distance sort | 353.9 ms | 1.4 ms |

### Choosing a distance method

| Option | Nearest 10 pickups | Plan |
|---|---|---|
| earthdistance + GiST index | 0.87 ms | index scan |
| PostGIS geography + GiST index | 1.30 ms | index scan |
| Haversine formula in SQL | 41.7 ms | reads every ride |

All three return the same order. I chose earthdistance: it's as fast as PostGIS but comes with PostgreSQL, so there's nothing extra to install. Haversine can't use an index.

## Design decisions

- **Settings from environment variables**, no secrets in the repo.
- **pre-commit**: ruff, mypy and a commit message check.
- **GitHub Actions** runs the same checks and the tests on every pull request.
- **Table and column names follow the spec**, using `db_table` and `db_column`.
- **The user model extends `AbstractUser`**, so passwords, the admin and token auth work as usual.
- **Unknown query parameters return 400**, so a typo like `?stauts=` isn't silently ignored.
- **Coordinate ranges and rider ≠ driver** are checked by the API and enforced by the database.
- **New passwords are checked** against the user's username, email and name.

## Bonus: trips longer than 1 hour

[`reports/long_trips.sql`](reports/long_trips.sql) counts trips whose pickup-to-dropoff duration was more than 1 hour, grouped by month and driver:

```sql
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
```

Run it against the seeded data:

```bash
docker compose exec -T db psql -U rides -d rides < reports/long_trips.sql
```

```
  Month  | Driver  | Count of Trips > 1 hr
---------+---------+-----------------------
 2026-08 | Chris Y |                     2
 2026-08 | Jose R  |                     2
 2026-08 | Lea G   |                     3
```

## Tests and checks

The tests run against PostgreSQL, since the distance sort and index checks need it.

| Test class | What it covers |
|---|---|
| `RideListTests` | What a ride list returns, and that it takes 3 queries |
| `RideDistanceOrderingTests` | Distance sort order, its validation, and that it can use the GiST index |
| `ErrorHandlingTests` | Every status code in the errors table |
| `RideFilterAndPaginationTests` | Filters, sorting and pagination on rides |
| `RideEventFilterTests` | Filtering ride events by ride |
| `UserApiTests` | Creating users, passwords and the admin role |
| `AdminPanelTests`, `RideModelTests`, `UserManagerTests` | The Django admin, deletes, and creating users outside the API |

## What I'd do next

Out of scope for this assessment, in order of impact:

1. **Faster pagination at scale.** The page count takes about 30 ms at 500,000 rides, and deep pages slow down (40-56 ms at offset 50,000). Cursor pagination fixes both.
2. **Stronger tokens.** DRF tokens never expire, are one per user and are stored in plain text. Expiring, hashed, per-device tokens (for example django-rest-knox) fix that.
3. **Rate limiting** with DRF throttling (429 past the limit), backed by Redis when there's more than one server.
4. **Load testing** once it's deployed. Locally it would only measure my machine and Django's dev server, not how the API holds up in production. For now, each request is measured instead: 3 indexed queries.
5. **Caching the page count** in Redis. The list itself changes too often to cache, and it's already fast.
6. **Background jobs** (Celery, or a nightly materialized view) for heavy reports like long trips. Nothing in the API is slow enough to need a queue yet.
7. **Logging.** Locally, the dev server already prints every request while unexpected errors are logged with a traceback. In production I'd add JSON logs with each request's duration and user, and send errors to Sentry.
