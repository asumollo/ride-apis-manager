from django.db import models
from django.db.models import Func


class LLToEarth(Func):
    # earthdistance's ll_to_earth(lat, lng): a point on Earth as 3D coordinates in meters
    function = "ll_to_earth"
    output_field = models.FloatField()


class EarthDistance(Func):
    # cube's <-> operator: straight-line distance between two earth points.
    arg_joiner = " <-> "
    template = "(%(expressions)s)"
    output_field = models.FloatField()
