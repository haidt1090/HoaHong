"""Add DepartmentResultValue table, migrate data JSON, remove the column."""

from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


def _convert_json_to_rows(apps, schema_editor):
    DepartmentResult = apps.get_model("examinations", "DepartmentResult")
    DepartmentResultValue = apps.get_model("examinations", "DepartmentResultValue")
    objs = []
    for result in DepartmentResult.objects.exclude(data={}):
        for key, value in result.data.items():
            objs.append(
                DepartmentResultValue(
                    result=result,
                    field_key=key,
                    value_number=_to_number(value),
                    value_text=_to_text(value),
                )
            )
    DepartmentResultValue.objects.bulk_create(objs, batch_size=500)


def _reverse_rows_to_json(apps, schema_editor):
    DepartmentResult = apps.get_model("examinations", "DepartmentResult")
    for result in DepartmentResult.objects.all():
        vals = result.values.all()
        result.data = {v.field_key: _from_value(v) for v in vals}
        result.save(update_fields=["data"])


def _to_number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return None


def _to_text(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _from_value(v):
    if v.value_number is not None:
        return float(v.value_number)
    return v.value_text


class Migration(migrations.Migration):
    dependencies = [
        (
            "examinations",
            "0009_remove_departmenttemplate_fields_config_and_more",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="DepartmentResultValue",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("field_key", models.CharField(max_length=100)),
                (
                    "value_number",
                    models.DecimalField(
                        blank=True, decimal_places=4, max_digits=15, null=True
                    ),
                ),
                ("value_text", models.TextField(blank=True)),
                (
                    "result",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="values",
                        to="examinations.departmentresult",
                    ),
                ),
            ],
            options={
                "ordering": ["field_key"],
                "indexes": [
                    models.Index(
                        fields=["field_key", "value_number"],
                        name="examination_field_k_8c764c_idx",
                    ),
                    models.Index(
                        fields=["field_key"],
                        name="examination_field_k_7c5018_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("result", "field_key"),
                        name="unique_value_per_result",
                    )
                ],
            },
        ),
        migrations.RunPython(_convert_json_to_rows, _reverse_rows_to_json),
        migrations.RemoveField(
            model_name="departmentresult",
            name="data",
        ),
    ]
