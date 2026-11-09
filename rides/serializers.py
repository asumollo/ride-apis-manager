from typing import Any

from django.contrib.auth import password_validation
from rest_framework import serializers

from rides.models import Ride, RideEvent, User


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id_user",
            "username",
            "role",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "password",
        ]

    def validate_password(self, value: str) -> str:
        password_validation.validate_password(value, self.instance)
        return value

    def create(self, validated_data: dict[str, Any]) -> User:
        return User.objects.create_user(**validated_data)

    def update(self, user: User, validated_data: dict[str, Any]) -> User:
        password = validated_data.pop("password", None)
        user = super().update(user, validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user


class RideEventSerializer(serializers.ModelSerializer):
    id_ride = serializers.PrimaryKeyRelatedField(source="ride", queryset=Ride.objects.all())

    class Meta:
        model = RideEvent
        fields = ["id_ride_event", "id_ride", "description", "created_at"]


class RideSerializer(serializers.ModelSerializer):
    id_rider = serializers.PrimaryKeyRelatedField(source="rider", queryset=User.objects.all())
    id_driver = serializers.PrimaryKeyRelatedField(source="driver", queryset=User.objects.all())
    rider = UserSerializer(read_only=True)
    driver = UserSerializer(read_only=True)
    todays_ride_events = serializers.SerializerMethodField()

    class Meta:
        model = Ride
        fields = [
            "id_ride",
            "status",
            "id_rider",
            "id_driver",
            "rider",
            "driver",
            "pickup_latitude",
            "pickup_longitude",
            "dropoff_latitude",
            "dropoff_longitude",
            "pickup_time",
            "todays_ride_events",
        ]

    def get_todays_ride_events(self, ride: Ride) -> list[dict[str, Any]]:
        events = getattr(ride, "todays_ride_events", [])
        return [RideEventSerializer(event).data for event in events]
