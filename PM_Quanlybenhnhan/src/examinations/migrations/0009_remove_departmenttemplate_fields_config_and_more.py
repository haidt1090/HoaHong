"""Add DepartmentField table, migrate fields_config JSON, remove the column."""

from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


def _convert_json_to_rows(apps, schema_editor):
    DepartmentTemplate = apps.get_model("examinations", "DepartmentTemplate")
    DepartmentField = apps.get_model("examinations", "DepartmentField")

    for template in DepartmentTemplate.objects.exclude(fields_config=[]):
        for idx, field_data in enumerate(template.fields_config or []):
            DepartmentField.objects.create(
                template=template,
                key=field_data.get("key", ""),
                label=field_data.get("label", ""),
                field_type=field_data.get("type", "text"),
                unit=field_data.get("unit", ""),
                required=field_data.get("required", False),
                order=field_data.get("order", idx + 1),
                normal_range=field_data.get("normal_range"),
                default_value=field_data.get("default_value"),
                default_price=field_data.get("default_price", 0),
                test_category=field_data.get("test_category", ""),
                options=field_data.get("options", []),
            )


def _reverse_rows_to_json(apps, schema_editor):
    DepartmentField = apps.get_model("examinations", "DepartmentField")
    DepartmentTemplate = apps.get_model("examinations", "DepartmentTemplate")

    for template in DepartmentTemplate.objects.all():
        rows = DepartmentField.objects.filter(template=template).order_by("order")
        template.fields_config = [r.as_config() for r in rows]
        template.save(update_fields=["fields_config"])


class Migration(migrations.Migration):
    dependencies = [
        ("examinations", "0008_change_uniq_constraint_to_template"),
    ]

    operations = [
        migrations.CreateModel(
            name="DepartmentField",
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
                ("key", models.CharField(max_length=100)),
                ("label", models.CharField(max_length=255)),
                (
                    "field_type",
                    models.CharField(
                        choices=[
                            ("text", "Text"),
                            ("number", "Number"),
                            ("select", "Select"),
                            ("multi_select", "Multi-select"),
                            ("boolean", "Boolean"),
                            ("date", "Date"),
                            ("textarea", "Textarea"),
                        ],
                        default="text",
                        max_length=20,
                    ),
                ),
                ("unit", models.CharField(blank=True, max_length=50)),
                ("required", models.BooleanField(default=False)),
                ("order", models.IntegerField(default=0)),
                ("normal_range", models.JSONField(blank=True, null=True)),
                ("default_value", models.JSONField(blank=True, null=True)),
                (
                    "default_price",
                    models.DecimalField(decimal_places=0, default=0, max_digits=12),
                ),
                ("test_category", models.CharField(blank=True, max_length=50)),
                ("options", models.JSONField(blank=True, default=list)),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fields",
                        to="examinations.departmenttemplate",
                    ),
                ),
            ],
            options={
                "ordering": ["order"],
                "indexes": [
                    models.Index(fields=["key"], name="examination_key_a5e42d_idx"),
                    models.Index(
                        fields=["template", "order"],
                        name="examination_templat_bdac86_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("template", "key"), name="unique_field_key_per_template"
                    )
                ],
            },
        ),
        migrations.RunPython(_convert_json_to_rows, _reverse_rows_to_json),
        migrations.RemoveField(
            model_name="departmenttemplate",
            name="fields_config",
        ),
    ]
