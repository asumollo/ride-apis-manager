from datetime import timedelta
from typing import Any

from django.db.models import Prefetch, ProtectedError, QuerySet
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from rides.filters import RideEventFilter, RideFilter, RideOrderingFilter
from rides.models import Ride, RideEvent, User
from rides.serializers import RideEventSerializer, RideSerializer, UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.order_by("id_user")
    serializer_class = UserSerializer

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "This user is on one or more rides and can't be deleted."},
                status=status.HTTP_409_CONFLICT,
            )


class RideViewSet(viewsets.ModelViewSet):
    queryset = Ride.objects.select_related("rider", "driver").order_by("id_ride")
    serializer_class = RideSerializer
    filter_backends = [DjangoFilterBackend, RideOrderingFilter]
    filterset_class = RideFilter
    ordering_fields = ["pickup_time"]

    def get_queryset(self) -> QuerySet[Ride]:
        since = timezone.now() - timedelta(hours=24)
        todays_events = RideEvent.objects.filter(created_at__gte=since).order_by("-created_at")
        prefetch = Prefetch("events", queryset=todays_events, to_attr="todays_ride_events")
        return super().get_queryset().prefetch_related(prefetch)


class RideEventViewSet(viewsets.ModelViewSet):
    queryset = RideEvent.objects.order_by("id_ride_event")
    serializer_class = RideEventSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = RideEventFilter
