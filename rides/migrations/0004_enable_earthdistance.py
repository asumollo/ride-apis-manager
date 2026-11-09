from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("rides", "0003_add_ride_list_indexes"),
    ]

    operations = [
        CreateExtension("cube"),
        CreateExtension("earthdistance"),
    ]
