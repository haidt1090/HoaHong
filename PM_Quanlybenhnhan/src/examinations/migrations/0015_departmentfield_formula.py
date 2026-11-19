# Generated manually for P2-S4c

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0014_department_parent"),
    ]

    operations = [
        migrations.AddField(
            model_name="departmentfield",
            name="formula",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Expression using {field_key} references. Example: {weight} / (({height} / 100) ^ 2). Supports IF(condition, true_val, false_val).",
            ),
        ),
        migrations.AlterField(
            model_name="departmentfield",
            name="field_type",
            field=models.CharField(
                choices=[
                    ("text", "Text"),
                    ("number", "Number"),
                    ("select", "Select"),
                    ("multi_select", "Multi-select"),
                    ("boolean", "Boolean"),
                    ("date", "Date"),
                    ("textarea", "Textarea"),
                    ("computed", "Computed"),
                ],
                default="text",
                max_length=20,
            ),
        ),
    ]
