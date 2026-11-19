# Generated manually for SyncJob.examination (single-exam sync)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0027_add_gender_overrides"),
        ("nationalsync", "0003_multi_environment"),
    ]

    operations = [
        migrations.AddField(
            model_name="syncjob",
            name="examination",
            field=models.ForeignKey(
                blank=True,
                help_text="Khi set: chỉ đồng bộ một lượt khám (không phải cả phạm vi).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="national_sync_jobs",
                to="examinations.examination",
            ),
        ),
    ]
