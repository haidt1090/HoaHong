"""Replace normal_range JSONField with normal_range_min + normal_range_max."""

from __future__ import annotations

from django.db import migrations, models


def _convert_json_to_columns(apps, schema_editor):
    DepartmentField = apps.get_model("examinations", "DepartmentField")
    for f in DepartmentField.objects.exclude(normal_range__isnull=True):
        nr = f.normal_range
        if isinstance(nr, dict):
            f.normal_range_min = nr.get("min")
            f.normal_range_max = nr.get("max")
            f.save(update_fields=["normal_range_min", "normal_range_max"])


def _reverse_columns_to_json(apps, schema_editor):
    DepartmentField = apps.get_model("examinations", "DepartmentField")
    for f in DepartmentField.objects.exclude(
        models.Q(normal_range_min__isnull=True)
        | models.Q(normal_range_max__isnull=True)
    ):
        nr = {}
        if f.normal_range_min is not None:
            nr["min"] = float(f.normal_range_min)
        if f.normal_range_max is not None:
            nr["max"] = float(f.normal_range_max)
        f.normal_range = nr if nr else None
        f.save(update_fields=["normal_range"])


class Migration(migrations.Migration):
    dependencies = [
        (
            "examinations",
            "0010_remove_departmentresult_data_departmentresultvalue",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="departmentfield",
            name="normal_range_max",
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=15, null=True
            ),
        ),
        migrations.AddField(
            model_name="departmentfield",
            name="normal_range_min",
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=15, null=True
            ),
        ),
        migrations.RunPython(_convert_json_to_columns, _reverse_columns_to_json),
        migrations.RemoveField(
            model_name="departmentfield",
            name="normal_range",
        ),
    ]
