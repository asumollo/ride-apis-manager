from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from rides.models import Ride, RideEvent, User

admin.site.site_url = "/api/"


@admin.register(User)
class RideUserAdmin(UserAdmin):
    list_display = ["username", "email", "role", "is_staff"]
    list_filter = ["role", "is_staff"]
    fieldsets = [*(UserAdmin.fieldsets or ()), ("Ride app", {"fields": ["role", "phone_number"]})]


@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = ["id_ride", "status", "rider", "driver", "pickup_time"]
    list_filter = ["status"]
    list_select_related = ["rider", "driver"]


@admin.register(RideEvent)
class RideEventAdmin(admin.ModelAdmin):
    list_display = ["id_ride_event", "ride", "description", "created_at"]
