from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from rides.models import Ride, RideEvent, User


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
