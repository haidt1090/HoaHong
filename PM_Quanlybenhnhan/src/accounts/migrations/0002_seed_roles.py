from __future__ import annotations

from django.db import migrations


ROLE_NAMES = [
    "admin",
    "doctor",
    "nurse",
    "labtech",
    "company_admin",
]


def seed_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for role in ROLE_NAMES:
        Group.objects.get_or_create(name=role)


def unseed_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLE_NAMES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_roles, unseed_roles),
    ]
