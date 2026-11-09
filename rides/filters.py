import django_filters

from rides.models import Ride


class RideFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Ride.Status.choices)
    rider_email = django_filters.CharFilter(field_name="rider__email")
    id_rider = django_filters.NumberFilter(field_name="rider_id")

    class Meta:
        model = Ride
        fields = ["status", "rider_email", "id_rider"]
