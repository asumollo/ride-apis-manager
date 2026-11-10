import random
from datetime import datetime, timedelta
from typing import Any, TypedDict

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandParser
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token

from rides.models import Ride, RideEvent, User

FIRST_NAMES = ["Chris", "Howard", "Randy", "Ana", "Maria", "Jose", "Lea", "Mark", "Grace", "Paolo"]
LAST_NAMES = ["Hernandez", "Young", "Walker", "Reyes", "Santos", "Cruz", "Garcia", "Lim", "Tan"]
STATUS_OF = {
    "Status changed to en-route": Ride.Status.EN_ROUTE,
    "Status changed to pickup": Ride.Status.PICKUP,
    "Status changed to dropoff": Ride.Status.DROPOFF,
}
BATCH = 5000


class RidePlan(TypedDict):
    ride: dict[str, Any]
    events: list[tuple[str, datetime]]


class Command(BaseCommand):
    help = "Create a demo admin, riders, drivers, and rides with realistic events."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--rides", type=int, default=200)
        parser.add_argument("--riders", type=int, default=50)
        parser.add_argument("--drivers", type=int, default=10)
        parser.add_argument("--days", type=int, default=90, help="Spread over the past N days.")
        parser.add_argument("--lat", type=float, default=14.5995, help="Center of the pickup area.")
        parser.add_argument("--lng", type=float, default=120.9842)
        parser.add_argument("--admin-password", default="admin12345")
        parser.add_argument("--seed", type=int, default=42, help="Repeatable on a fresh database.")
        parser.add_argument("--reset", action="store_true", help="Delete ALL rides first.")

    def handle(self, *args: Any, **opts: Any) -> None:
        rng = random.Random(opts["seed"])
        with transaction.atomic():
            if opts["reset"]:
                with connection.cursor() as cursor:
                    # Django's foreign keys are checked at commit; run those checks now,
                    # since TRUNCATE refuses to start while any are still pending.
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                    cursor.execute("TRUNCATE ride_event, ride RESTART IDENTITY")
            admin, created = self.ensure_admin(opts["admin_password"])
            riders = self.ensure_users("rider", opts["riders"], rng)
            drivers = self.ensure_users("driver", opts["drivers"], rng)
            rides, events, recent = self.create_rides(rng, riders, drivers, opts)
        token, _ = Token.objects.get_or_create(user=admin)

        if created:
            self.stdout.write(f"Admin: admin / {opts['admin_password']} (local testing only)")
        else:
            self.stdout.write("Admin: admin already existed, so its password wasn't changed")
        self.stdout.write(f"Token: {token.key}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {rides:,} rides and {events:,} events for {len(riders)} riders "
                f"and {len(drivers)} drivers. {recent:,} rides have events in the last 24 hours."
            )
        )

    def ensure_admin(self, password: str) -> tuple[User, bool]:
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@example.com", "is_staff": True, "is_superuser": True},
        )
        if created:
            admin.set_password(password)
        admin.role = User.Role.ADMIN
        admin.save()
        return admin, created

    def ensure_users(self, prefix: str, count: int, rng: random.Random) -> list[User]:
        names = [f"{prefix}{i:03d}" for i in range(1, count + 1)]
        existing = set(User.objects.filter(username__in=names).values_list("username", flat=True))
        User.objects.bulk_create(
            User(
                username=name,
                email=f"{name}@example.com",
                first_name=rng.choice(FIRST_NAMES),
                last_name=rng.choice(LAST_NAMES),
                password=make_password(None),  # can't log in
            )
            for name in names
            if name not in existing
        )
        return list(User.objects.filter(username__in=names))

    def create_rides(
        self, rng: random.Random, riders: list[User], drivers: list[User], opts: dict[str, Any]
    ) -> tuple[int, int, int]:
        now = timezone.now()
        made = events_made = recent = 0
        while made < opts["rides"]:
            size = min(BATCH, opts["rides"] - made)
            plans = [self.plan_ride(rng, now, opts) for _ in range(size)]
            rides = Ride.objects.bulk_create(
                Ride(rider=rng.choice(riders), driver=rng.choice(drivers), **plan["ride"])
                for plan in plans
            )
            events = [
                RideEvent(ride=ride, description=description, created_at=at)
                for ride, plan in zip(rides, plans, strict=True)
                for description, at in plan["events"]
            ]
            RideEvent.objects.bulk_create(events, batch_size=BATCH)
            made += len(rides)
            events_made += len(events)
            recent += sum(1 for plan in plans if plan["events"][-1][1] >= now - timedelta(hours=24))
            if opts["rides"] >= 50_000 and made % 50_000 == 0:
                self.stdout.write(f"  {made:,} rides...")
        return made, events_made, recent

    def plan_ride(self, rng: random.Random, now: datetime, opts: dict[str, Any]) -> RidePlan:
        roll = rng.random()
        if roll < 0.10:  # en route to the rider
            pickup_time = now + timedelta(minutes=rng.uniform(0, 5))
        elif roll < 0.20:  # picked up, not dropped off yet
            pickup_time = now - timedelta(minutes=rng.uniform(5, 15))
        elif roll < 0.35:  # finished today, so todays_ride_events has data
            pickup_time = now - timedelta(hours=rng.uniform(3, 24))
        else:
            pickup_time = now - timedelta(days=rng.uniform(1, opts["days"]))
        en_route_at = pickup_time - timedelta(minutes=rng.uniform(5, 15))
        pickup_at = pickup_time + timedelta(minutes=rng.uniform(0, 5))
        dropoff_at = pickup_at + timedelta(minutes=rng.uniform(20, 120))
        events = [
            (description, at)
            for description, at in [
                ("Status changed to en-route", en_route_at),
                ("Status changed to pickup", pickup_at),
                ("Status changed to dropoff", dropoff_at),
            ]
            if at <= now  # a ride in progress hasn't reached its later steps yet
        ]
        lat = opts["lat"] + rng.uniform(-0.15, 0.15)
        lng = opts["lng"] + rng.uniform(-0.15, 0.15)
        return {
            "ride": {
                "status": STATUS_OF[events[-1][0]],
                "pickup_time": pickup_time,
                "pickup_latitude": lat,
                "pickup_longitude": lng,
                "dropoff_latitude": lat + rng.uniform(-0.1, 0.1),
                "dropoff_longitude": lng + rng.uniform(-0.1, 0.1),
            },
            "events": events,
        }
