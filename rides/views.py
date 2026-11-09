from datetime import timedelta
from typing import Any

from django.db.models import Prefetch, ProtectedError, QuerySet
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.response import Response

from rides.filters import RideEventFilter, RideFilter, RideOrderingFilter
from rides.models import Ride, RideEvent, User
from rides.serializers import RideEventSerializer, RideSerializer, UserSerializer


class StrictModelViewSet(viewsets.ModelViewSet):
    # Rejects unknown or repeated query parameters
    extra_query_params: tuple[str, ...] = ()

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)
        allowed = {"format", *self.extra_query_params}
        filterset_class = getattr(self, "filterset_class", None)
        if filterset_class is not None:
            allowed.update(filterset_class.base_filters)
        for backend in self.filter_backends:
            if issubclass(backend, OrderingFilter):
                allowed.add(backend.ordering_param)
        if self.paginator is not None:
            allowed.update(
                name
                for name in (
                    getattr(self.paginator, "page_query_param", None),
                    getattr(self.paginator, "page_size_query_param", None),
                )
                if name
            )
        unknown = sorted(set(request.query_params) - allowed)
        if unknown:
            message = f"Unknown query parameter. Use one of: {', '.join(sorted(allowed))}."
            raise ValidationError({name: [message] for name in unknown})
        params = request.query_params
        repeated = sorted(name for name in params if len(params.getlist(name)) > 1)
        if repeated:
            raise ValidationError({name: ["Pass this parameter once."] for name in repeated})


class UserViewSet(StrictModelViewSet):
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


class RideViewSet(StrictModelViewSet):
    queryset = Ride.objects.select_related("rider", "driver").order_by("id_ride")
    serializer_class = RideSerializer
    filter_backends = [DjangoFilterBackend, RideOrderingFilter]
    filterset_class = RideFilter
    ordering_fields = ["pickup_time"]
    extra_query_params = ("lat", "lng")

    def get_queryset(self) -> QuerySet[Ride]:
        since = timezone.now() - timedelta(hours=24)
        todays_events = RideEvent.objects.filter(created_at__gte=since).order_by("-created_at")
        prefetch = Prefetch("events", queryset=todays_events, to_attr="todays_ride_events")
        return super().get_queryset().prefetch_related(prefetch)


class RideEventViewSet(StrictModelViewSet):
    queryset = RideEvent.objects.order_by("id_ride_event")
    serializer_class = RideEventSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = RideEventFilter
