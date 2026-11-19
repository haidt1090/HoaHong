"""Seed default departments on first migration (Sprint 4 technical note)."""

from __future__ import annotations

from django.db import migrations

DEFAULT_DEPARTMENTS = [
    {
        "name": "Khám lâm sàng",
        "code": "kham_lam_sang",
        "category": "clinical",
    },
    {
        "name": "Xét nghiệm",
        "code": "xet_nghiem",
        "category": "para_clinical",
    },
    {
        "name": "X-Quang",
        "code": "x_quang",
        "category": "para_clinical",
    },
    {
        "name": "Siêu âm",
        "code": "sieu_am",
        "category": "para_clinical",
    },
]


def seed_departments(apps, schema_editor):
    Department = apps.get_model("examinations", "Department")
    for entry in DEFAULT_DEPARTMENTS:
        Department.objects.get_or_create(
            code=entry["code"],
            defaults={
                "name": entry["name"],
                "category": entry["category"],
            },
        )


def unseed_departments(apps, schema_editor):
    Department = apps.get_model("examinations", "Department")
    codes = [entry["code"] for entry in DEFAULT_DEPARTMENTS]
    Department.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("examinations", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_departments, unseed_departments),
    ]
