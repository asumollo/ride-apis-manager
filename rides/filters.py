from collections.abc import Sequence

import django_filters
from django.db.models import QuerySet
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.views import APIView

from rides.models import Ride


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
