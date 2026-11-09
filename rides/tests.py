from datetime import timedelta
from unittest.mock import patch

from django.db import OperationalError, connection
from django.db.models import ProtectedError
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.generics import GenericAPIView
from rest_framework.test import APITestCase

from rides.models import Ride, RideEvent, User
from rides.urls import router


def explain(sql):
    # Tiny test tables would always use a seq scan
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL enable_seqscan = off")
        cursor.execute("EXPLAIN " + sql)
        return "\n".join(row[0] for row in cursor.fetchall())


class RideListTests(APITestCase):
    """
    What a ride list page returns or how many queries it takes
    """

    admin: User

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="pass12345!", role="admin"
        )
        rider = User.objects.create_user(username="ana", email="ana@example.com")
        driver = User.objects.create_user(username="chris", email="chris@example.com")
        now = timezone.now()
        for i in range(5):
            ride = Ride.objects.create(
                status=Ride.Status.PICKUP,
                rider=rider,
                driver=driver,
                pickup_latitude=14.60,
                pickup_longitude=121.00,
                dropoff_latitude=14.55,
                dropoff_longitude=121.05,
                pickup_time=now + timedelta(hours=i),
            )
            RideEvent.objects.create(
                ride=ride, description="Status changed to pickup", created_at=now
            )
            RideEvent.objects.create(
                ride=ride, description="Old event", created_at=now - timedelta(days=2)
            )

    def setUp(self):
        self.client.force_authenticate(self.admin)

    def test_list_uses_three_queries(self):
        # 1 COUNT for pagination, 1 rides JOIN rider and driver, 1 for today's events.
        with self.assertNumQueries(3):
            response = self.client.get(reverse("ride-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 5)

    def test_todays_ride_events_only_has_last_24_hours(self):
        response = self.client.get(reverse("ride-list"))
        events = response.data["results"][0]["todays_ride_events"]
        self.assertEqual([e["description"] for e in events], ["Status changed to pickup"])

    def test_todays_events_query_can_use_an_index(self):
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(reverse("ride-list"))
        events_sql = next(q["sql"] for q in ctx.captured_queries if 'FROM "ride_event"' in q["sql"])
        self.assertIn("ride_event_ride_created_idx", explain(events_sql))

    def test_browsable_api_renders(self):
        pages = [reverse("api-root")]
        for _prefix, viewset, basename in router.registry:
            pages.append(reverse(f"{basename}-list"))
            assert issubclass(viewset, GenericAPIView) and viewset.queryset is not None
            obj = viewset.queryset.first()
            assert obj is not None, f"Add a {basename} to setUpTestData"
            pages.append(reverse(f"{basename}-detail", args=[obj.pk]))

        for url in pages:
            with self.subTest(url=url):
                response = self.client.get(url, HTTP_ACCEPT="text/html")
                self.assertEqual(response.status_code, 200)


class RideDistanceOrderingTests(APITestCase):
    """
    Anything about ?ordering=distance (the lat/lng check, the order, the index)
    """

    admin: User
    url: str

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="pass12345!", role="admin"
        )
        rider = User.objects.create_user(username="ana", email="ana@example.com")
        driver = User.objects.create_user(username="chris", email="chris@example.com")
        # From (14.60, 121.00): about 56 km, 1 km and 11 km away, created out of order
        for lat in (15.10, 14.61, 14.70):
            Ride.objects.create(
                status=Ride.Status.PICKUP,
                rider=rider,
                driver=driver,
                pickup_latitude=lat,
                pickup_longitude=121.00,
                dropoff_latitude=lat,
                dropoff_longitude=121.00,
                pickup_time=timezone.now(),
            )
        cls.url = reverse("ride-list")

    def setUp(self):
        self.client.force_authenticate(self.admin)

    def test_orders_nearest_pickup_first(self):
        response = self.client.get(
            self.url, {"ordering": "distance", "lat": "14.60", "lng": "121.00"}
        )
        self.assertEqual(response.status_code, 200)
        lats = [ride["pickup_latitude"] for ride in response.data["results"]]
        self.assertEqual(lats, [14.61, 14.70, 15.10])

    def test_requires_lat_and_lng(self):
        response = self.client.get(self.url, {"ordering": "distance"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {"lat", "lng"})

    def test_rejects_out_of_range_and_non_numbers(self):
        for params in (
            {"lat": "91", "lng": "0"},
            {"lat": "0", "lng": "abc"},
            {"lat": "nan", "lng": "0"},
        ):
            with self.subTest(params=params):
                response = self.client.get(self.url, {"ordering": "distance", **params})
                self.assertEqual(response.status_code, 400)

    def test_rejects_farthest_first(self):
        response = self.client.get(
            self.url, {"ordering": "-distance", "lat": "14.6", "lng": "121.0"}
        )
        self.assertEqual(response.status_code, 400)

    def test_distance_query_can_use_the_gist_index(self):
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(self.url, {"ordering": "distance", "lat": "14.6", "lng": "121.0"})
        rides_sql = next(q["sql"] for q in ctx.captured_queries if "ll_to_earth" in q["sql"])
        self.assertIn("ride_pickup_earth_idx", explain(rides_sql))


class ErrorHandlingTests(APITestCase):
    """
    Error handling across the API: a new status code, or a new rule on ride data
    """

    admin: User
    other: User
    rider: User
    driver: User
    ride: Ride
    url: str

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="pass12345!", role="admin"
        )
        cls.other = User.objects.create_user(username="ops", email="ops@example.com")
        cls.rider = User.objects.create_user(username="ana", email="ana@example.com")
        cls.driver = User.objects.create_user(username="chris", email="chris@example.com")
        cls.ride = Ride.objects.create(
            status=Ride.Status.PICKUP,
            rider=cls.rider,
            driver=cls.driver,
            pickup_latitude=14.6,
            pickup_longitude=121.0,
            dropoff_latitude=14.5,
            dropoff_longitude=121.1,
            pickup_time=timezone.now(),
        )
        cls.url = reverse("ride-list")

    def ride_payload(self, **overrides):
        payload = {
            "status": "pickup",
            "id_rider": self.rider.pk,
            "id_driver": self.driver.pk,
            "pickup_latitude": 14.6,
            "pickup_longitude": 121.0,
            "dropoff_latitude": 14.5,
            "dropoff_longitude": 121.1,
            "pickup_time": "2026-11-08T09:00:00Z",
        }
        return {**payload, **overrides}

    def test_missing_token_is_401(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_non_admin_is_403(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_unknown_ride_is_404(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("ride-detail", args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_invalid_ride_fields_are_400(self):
        self.client.force_authenticate(self.admin)
        payload = self.ride_payload(status="pikup", pickup_latitude=91, dropoff_longitude=-181)
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {"status", "pickup_latitude", "dropoff_longitude"})

    def test_rider_and_driver_must_differ(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.url, self.ride_payload(id_driver=self.rider.pk), format="json"
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            reverse("ride-detail", args=[self.ride.pk]), {"id_driver": self.rider.pk}
        )
        self.assertEqual(response.status_code, 400)

    def test_malformed_json_is_400(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, '{"status": ', content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_deleting_a_user_with_rides_is_409(self):
        self.client.force_authenticate(self.admin)
        response = self.client.delete(reverse("user-detail", args=[self.driver.pk]))
        self.assertEqual(response.status_code, 409)
        self.assertTrue(User.objects.filter(pk=self.driver.pk).exists())

    def test_unexpected_error_is_json_500(self):
        self.client.force_authenticate(self.admin)
        with (
            patch("rides.views.RideViewSet.get_queryset", side_effect=RuntimeError("boom")),
            self.assertLogs("rides.exceptions", level="ERROR"),
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "Something went wrong on our side."})

    def test_database_outage_is_503(self):
        self.client.force_authenticate(self.admin)
        with (
            patch("rides.views.RideViewSet.get_queryset", side_effect=OperationalError("down")),
            self.assertLogs("rides.exceptions", level="ERROR"),
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)


class RideFilterAndPaginationTests(APITestCase):
    """
    Filters, sort fields or page settings on /api/rides/
    """

    admin: User
    ana: User
    ben: User
    url: str

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="pass12345!", role="admin"
        )
        cls.ana = User.objects.create_user(username="ana", email="Ana.Reyes@Example.com")
        cls.ben = User.objects.create_user(username="ben", email="ben@example.com")
        driver = User.objects.create_user(username="chris", email="chris@example.com")
        statuses = [Ride.Status.PICKUP, Ride.Status.DROPOFF, Ride.Status.EN_ROUTE]
        base = timezone.now()
        # 12 rides; every 3 share a pickup_time, so sorting needs the id_ride tie-breaker
        for i in range(12):
            Ride.objects.create(
                status=statuses[i % 3],
                rider=cls.ana if i % 2 == 0 else cls.ben,
                driver=driver,
                pickup_latitude=14.6,
                pickup_longitude=121.0,
                dropoff_latitude=14.5,
                dropoff_longitude=121.1,
                pickup_time=base + timedelta(hours=i % 4),
            )
        cls.url = reverse("ride-list")

    def setUp(self):
        self.client.force_authenticate(self.admin)

    def all_pages(self, params):
        ids, page = [], 1
        while True:
            data = self.client.get(self.url, {**params, "page": page}).data
            ids += [ride["id_ride"] for ride in data["results"]]
            if data["next"] is None:
                return ids
            page += 1

    def test_filter_by_status(self):
        data = self.client.get(self.url, {"status": "dropoff"}).data
        self.assertEqual(data["count"], 4)
        self.assertEqual({ride["status"] for ride in data["results"]}, {"dropoff"})

    def test_filter_by_rider_email_matches_case(self):
        data = self.client.get(self.url, {"rider_email": "Ana.Reyes@example.com"}).data
        self.assertEqual(data["count"], 6)
        self.assertEqual({ride["id_rider"] for ride in data["results"]}, {self.ana.pk})
        data = self.client.get(self.url, {"rider_email": "ana.reyes@example.com"}).data
        self.assertEqual(data["count"], 0)

    def test_filter_by_rider_id(self):
        data = self.client.get(self.url, {"id_rider": self.ben.pk}).data
        self.assertEqual(data["count"], 6)

    def test_unknown_status_is_400(self):
        self.assertEqual(self.client.get(self.url, {"status": "pikup"}).status_code, 400)

    def test_pagination(self):
        first = self.client.get(self.url).data
        self.assertEqual((first["count"], len(first["results"])), (12, 10))
        self.assertIsNotNone(first["next"])
        second = self.client.get(self.url, {"page": 2}).data
        self.assertEqual(len(second["results"]), 2)
        self.assertIsNone(second["next"])
        self.assertEqual(len(self.client.get(self.url, {"page_size": 5}).data["results"]), 5)
        self.assertEqual(self.client.get(self.url, {"page": 99}).status_code, 404)

    def test_pickup_time_sorting_covers_every_ride_once(self):
        for ordering in ("pickup_time", "-pickup_time"):
            with self.subTest(ordering=ordering):
                ids = self.all_pages({"ordering": ordering, "page_size": 5})
                self.assertEqual(sorted(ids), sorted(Ride.objects.values_list("pk", flat=True)))

    def test_pickup_time_sorting_has_a_tie_breaker(self):
        # Rides with the same pickup_time need a fixed order, or pages can repeat or skip them
        for ordering, direction in (("pickup_time", "ASC"), ("-pickup_time", "DESC")):
            with self.subTest(ordering=ordering), CaptureQueriesContext(connection) as ctx:
                self.client.get(self.url, {"ordering": ordering})
            sql = next(q["sql"] for q in ctx.captured_queries if "LIMIT" in q["sql"])
            self.assertIn(
                f'ORDER BY "ride"."pickup_time" {direction}, "ride"."id_ride" {direction}', sql
            )

    def test_pickup_time_sorting_can_use_an_index(self):
        for params, index in (
            ({"ordering": "pickup_time"}, "ride_pickup_time_idx"),
            ({"ordering": "-pickup_time"}, "ride_pickup_time_idx"),
            ({"status": "pickup", "ordering": "pickup_time"}, "ride_status_pickup_time_idx"),
        ):
            with self.subTest(params=params), CaptureQueriesContext(connection) as ctx:
                self.client.get(self.url, params)
            sql = next(q["sql"] for q in ctx.captured_queries if "LIMIT" in q["sql"])
            self.assertIn(index, explain(sql))


class RideEventFilterTests(APITestCase):
    """
    Filters on /api/ride-events/
    """

    admin: User
    rides: list[Ride]
    url: str

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="pass12345!", role="admin"
        )
        rider = User.objects.create_user(username="ana", email="ana@example.com")
        driver = User.objects.create_user(username="chris", email="chris@example.com")
        cls.rides = [
            Ride.objects.create(
                status=Ride.Status.DROPOFF,
                rider=rider,
                driver=driver,
                pickup_latitude=14.6,
                pickup_longitude=121.0,
                dropoff_latitude=14.5,
                dropoff_longitude=121.1,
                pickup_time=timezone.now(),
            )
            for _ in range(2)
        ]
        for ride in cls.rides:
            for step in ("en-route", "pickup", "dropoff"):
                RideEvent.objects.create(ride=ride, description=f"Status changed to {step}")
        cls.url = reverse("rideevent-list")

    def setUp(self):
        self.client.force_authenticate(self.admin)

    def test_filter_by_ride_returns_its_full_history(self):
        ride = self.rides[0]
        data = self.client.get(self.url, {"id_ride": ride.pk}).data
        self.assertEqual(data["count"], 3)
        self.assertEqual({event["id_ride"] for event in data["results"]}, {ride.pk})

    def test_bad_ride_id_is_400(self):
        self.assertEqual(self.client.get(self.url, {"id_ride": "abc"}).status_code, 400)


class AdminPanelTests(TestCase):
    """
    What the Django admin shows
    """

    def test_changelists_load(self):
        boss = User.objects.create_superuser("boss", "boss@example.com", "pass12345!")
        self.client.force_login(boss)
        for model in ("user", "ride", "rideevent"):
            with self.subTest(model=model):
                response = self.client.get(reverse(f"admin:rides_{model}_changelist"))
                self.assertEqual(response.status_code, 200)


class UserApiTests(APITestCase):
    """
    What /api/users/ accepts or returns
    """

    admin: User
    url: str

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="pass12345!", role="admin"
        )
        cls.url = reverse("user-list")

    def setUp(self):
        self.client.force_authenticate(self.admin)

    def test_created_user_can_log_in(self):
        payload = {"username": "lea", "email": "lea@example.com", "password": "rides-are-fun-42"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.data)
        self.assertTrue(User.objects.get(username="lea").check_password("rides-are-fun-42"))

    def test_weak_password_is_400(self):
        payload = {"username": "lea", "email": "lea@example.com", "password": "123"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)

    def test_user_without_password_cannot_log_in(self):
        payload = {"username": "lea", "email": "lea@example.com"}
        self.assertEqual(self.client.post(self.url, payload, format="json").status_code, 201)
        self.assertFalse(User.objects.get(username="lea").has_usable_password())

    def test_patch_changes_password(self):
        user = User.objects.create_user(username="lea", email="lea@example.com")
        url = reverse("user-detail", args=[user.pk])
        response = self.client.patch(url, {"password": "rides-are-fun-42"}, format="json")
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("rides-are-fun-42"))

    def test_password_cant_be_close_to_the_username(self):
        payload = {"username": "lea.reyes", "email": "lea@example.com", "password": "lea.reyes1"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)

    def test_superuser_can_use_the_api(self):
        boss = User.objects.create_superuser("boss", "boss@example.com", "pass12345!")
        self.assertEqual(boss.role, User.Role.ADMIN)
        self.client.force_authenticate(boss)
        self.assertEqual(self.client.get(self.url).status_code, 200)


class RideModelTests(TestCase):
    """
    What deleting a ride or a user does to the rows linked to it
    """

    ride: Ride

    @classmethod
    def setUpTestData(cls):
        rider = User.objects.create_user(username="ana", email="ana@example.com")
        driver = User.objects.create_user(username="chris", email="chris@example.com")
        cls.ride = Ride.objects.create(
            status=Ride.Status.PICKUP,
            rider=rider,
            driver=driver,
            pickup_latitude=14.6,
            pickup_longitude=121.0,
            dropoff_latitude=14.5,
            dropoff_longitude=121.1,
            pickup_time=timezone.now(),
        )
        RideEvent.objects.create(ride=cls.ride, description="Status changed to pickup")

    def test_deleting_a_ride_deletes_its_events(self):
        self.ride.delete()
        self.assertFalse(RideEvent.objects.exists())

    def test_user_on_a_ride_cant_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.ride.driver.delete()


class UserManagerTests(TestCase):
    """
    How users are created outside the API
    """

    def test_superuser_gets_admin_role(self):
        user = User.objects.create_superuser("boss", "boss@example.com", "pass12345!")
        self.assertEqual(user.role, User.Role.ADMIN)
