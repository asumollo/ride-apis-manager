from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets

from rides.filters import RideFilter
from rides.models import Ride, RideEvent, User
from rides.serializers import RideEventSerializer, RideSerializer, UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.order_by("id_user")
    serializer_class = UserSerializer


class RideViewSet(viewsets.ModelViewSet):
    queryset = Ride.objects.select_related("rider", "driver").order_by("id_ride")
    serializer_class = RideSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = RideFilter


class RideEventViewSet(viewsets.ModelViewSet):
    queryset = RideEvent.objects.order_by("id_ride_event")
    serializer_class = RideEventSerializer
