# Generated manually for P2-S4b

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0013_add_exportjob_s6"),
    ]

    operations = [
        migrations.AddField(
            model_name="department",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                help_text="Parent department for hierarchical grouping.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="children",
                to="examinations.department",
            ),
        ),
    ]
