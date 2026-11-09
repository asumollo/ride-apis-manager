from typing import Any, ClassVar

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.contrib.postgres.indexes import GistIndex
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from rides.geo import LLToEarth

LATITUDE = [MinValueValidator(-90), MaxValueValidator(90)]
LONGITUDE = [MinValueValidator(-180), MaxValueValidator(180)]


class UserManager(DjangoUserManager["User"]):
    # createsuperuser should also get API access
    def create_superuser(
        self,
        username: str,
        email: str | None = None,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        extra_fields.setdefault("role", User.Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        OTHER = "other", "Other"

    id_user = models.AutoField(primary_key=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OTHER)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)

    objects: ClassVar[UserManager] = UserManager()

    class Meta:
        db_table = "users"


class Ride(models.Model):
    class Status(models.TextChoices):
        EN_ROUTE = "en-route", "En route"
        PICKUP = "pickup", "Pickup"
        DROPOFF = "dropoff", "Dropoff"

    id_ride = models.AutoField(primary_key=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    rider = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="rides_as_rider",
        db_column="id_rider",
    )
    driver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="rides_as_driver",
        db_column="id_driver",
    )
    pickup_latitude = models.FloatField(validators=LATITUDE)
    pickup_longitude = models.FloatField(validators=LONGITUDE)
    dropoff_latitude = models.FloatField(validators=LATITUDE)
    dropoff_longitude = models.FloatField(validators=LONGITUDE)
    pickup_time = models.DateTimeField()

    class Meta:
        db_table = "ride"
        indexes = [
            # ?ordering=pickup_time (id_ride is the tie-breaker)
            models.Index(fields=["pickup_time", "id_ride"], name="ride_pickup_time_idx"),
            # ?status=...&ordering=pickup_time
            models.Index(
                fields=["status", "pickup_time", "id_ride"], name="ride_status_pickup_time_idx"
            ),
            # ?ordering=distance: nearest-first walk over pickup points
            GistIndex(
                LLToEarth("pickup_latitude", "pickup_longitude"), name="ride_pickup_earth_idx"
            ),
        ]


class RideEvent(models.Model):
    id_ride_event = models.AutoField(primary_key=True)
    ride = models.ForeignKey(
        Ride,
        on_delete=models.CASCADE,
        related_name="events",
        db_column="id_ride",
        db_index=False,  # covered by ride_event_ride_created_idx
    )
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "ride_event"
        indexes = [
            models.Index(fields=["ride", "created_at"], name="ride_event_ride_created_idx"),
        ]
