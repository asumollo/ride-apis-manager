# Run with: python manage.py shell < benchmarks/bench_prefetch.py
# SHOW_SQL=10 prints each version's queries for 10 rides instead of timing them.
import os
import re
import statistics
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import sqlparse
from django.db import connection, reset_queries
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from rides.models import Ride
from rides.serializers import RideEventSerializer, RideSerializer
from rides.views import RideViewSet

RUNS = 20


class NaiveRideSerializer(RideSerializer):
    # The "before" version: one events query per ride
    def get_todays_ride_events(self, ride: Ride) -> list[dict[str, Any]]:
        since = timezone.now() - timedelta(hours=24)
        events = ride.events.filter(created_at__gte=since).order_by("-created_at")
        return [RideEventSerializer(event).data for event in events]


def ours(n: int) -> Any:
    return RideSerializer(RideViewSet().get_queryset()[:n], many=True).data


def prefetch_only(n: int) -> Any:
    # select_related(None) drops the rider/driver join, keeps the prefetch
    rides = RideViewSet().get_queryset().select_related(None)[:n]
    return RideSerializer(rides, many=True).data


def select_related_only(n: int) -> Any:
    rides = Ride.objects.select_related("rider", "driver").order_by("id_ride")[:n]
    return NaiveRideSerializer(rides, many=True).data


def neither(n: int) -> Any:
    rides = Ride.objects.order_by("id_ride")[:n]
    return NaiveRideSerializer(rides, many=True).data


VERSIONS: list[tuple[str, Callable[[int], Any]]] = [
    ("ours (select_related + prefetch)", ours),
    ("prefetch only", prefetch_only),
    ("select_related only", select_related_only),
    ("neither", neither),
]


def measure(fn: Callable[[int], Any], n: int) -> tuple[int, float, float]:
    fn(n)  # warm-up
    walls, cpus = [], []
    queries = 0
    for _ in range(RUNS):
        reset_queries()  # the query log caps at 9000 entries
        with CaptureQueriesContext(connection) as ctx:
            wall, cpu = time.perf_counter(), time.process_time()
            fn(n)
            walls.append((time.perf_counter() - wall) * 1000)
            cpus.append((time.process_time() - cpu) * 1000)
        queries = len(ctx.captured_queries)
    return queries, statistics.median(walls), statistics.median(cpus)


def show_sql(n: int) -> None:
    for label, fn in VERSIONS:
        with CaptureQueriesContext(connection) as ctx:
            fn(n)
        print(f"===== {label}: {len(ctx.captured_queries)} queries for {n} rides =====\n")
        for i, query in enumerate(ctx.captured_queries, 1):
            # Hide the long column list so the FROM/JOIN/WHERE stands out
            sql = re.sub(r"^SELECT .*? FROM", "SELECT ... FROM", query["sql"], count=1, flags=re.S)
            print(f"-- {i}")
            print(sqlparse.format(sql, reindent=True) + "\n")


def run() -> None:
    print(f"{connection.settings_dict['NAME']}, median of {RUNS} runs\n")
    header = f"{'page':>5}  {'version':<34}{'queries':>8}{'total ms':>10}{'python cpu ms':>15}"
    print(f"{header}{'waiting on db ms':>18}")
    for n in (10, 100):
        for label, fn in VERSIONS:
            queries, wall, cpu = measure(fn, n)
            row = f"{n:>5}  {label:<34}{queries:>8}{wall:>10.1f}{cpu:>15.1f}"
            print(f"{row}{wall - cpu:>18.1f}")
        print()


if os.environ.get("SHOW_SQL"):
    show_sql(int(os.environ["SHOW_SQL"]))
else:
    run()
