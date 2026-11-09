import math
from collections.abc import Sequence
from typing import Any

import django_filters
from django.db.models import QuerySet, Value
from django.http import QueryDict
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.views import APIView

from rides.geo import EarthDistance, LLToEarth
from rides.models import Ride, RideEvent


class RideFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Ride.Status.choices)
    rider_email = django_filters.CharFilter(field_name="rider__email")
    id_rider = django_filters.NumberFilter(field_name="rider_id")

    class Meta:
        model = Ride
        fields = ["status", "rider_email", "id_rider"]


class StableOrderingFilter(OrderingFilter):
    # Tie-break on id_ride in the sort's direction, so pages stay stable
    def get_ordering(
        self, request: Request, queryset: QuerySet[Ride], view: APIView
    ) -> Sequence[str] | None:
        ordering = super().get_ordering(request, queryset, view)
        if ordering and ordering[-1].lstrip("-") != "id_ride":
            tie_breaker = "-id_ride" if ordering[0].startswith("-") else "id_ride"
            ordering = [*ordering, tie_breaker]
        return ordering


class RideOrderingFilter(StableOrderingFilter):
    # ?ordering=distance&lat=..&lng=.. sorts nearest pickup first.
    def filter_queryset(
        self, request: Request, queryset: QuerySet[Any], view: APIView
    ) -> QuerySet[Any]:
        ordering = request.query_params.get(self.ordering_param)
        # DRF ignores unknown fields
        fields = getattr(view, "ordering_fields", [])
        allowed = [*fields, *(f"-{field}" for field in fields), "distance"]
        if ordering and ordering not in allowed:
            raise ValidationError({"ordering": [f"Use one of: {', '.join(allowed)}."]})
        if ordering != "distance":
            return super().filter_queryset(request, queryset, view)
        lat, lng = parse_point(request.query_params)
        distance = EarthDistance(
            LLToEarth("pickup_latitude", "pickup_longitude"),
            LLToEarth(Value(lat), Value(lng)),
        )
        # no id_ride tie-break: it stops Postgres using the GiST index
        return queryset.order_by(distance)


def parse_point(params: QueryDict) -> list[float]:
    errors: dict[str, list[str]] = {}
    values: list[float] = []
    for name, limit in (("lat", 90), ("lng", 180)):
        raw = params.get(name, "")
        try:
            value = float(raw)
        except ValueError:
            errors[name] = ["A number is required when ordering by distance."]
            continue
        if not math.isfinite(value) or not -limit <= value <= limit:
            errors[name] = [f"Must be between -{limit} and {limit}."]
            continue
        values.append(value)
    if errors:
        raise ValidationError(errors)
    return values


class RideEventFilter(django_filters.FilterSet):
    id_ride = django_filters.NumberFilter(field_name="ride_id")

    class Meta:
        model = RideEvent
        fields = ["id_ride"]
