"""
Sprint 2a — StaffAssignment model for linking Nurse/LabTech to companies.
"""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_user_date_joined_alter_user_groups"),
    ]

    operations = [
        migrations.CreateModel(
            name="StaffAssignment",
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
                (
                    "assigned_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="staff_assignments",
                        to="accounts.company",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        limit_choices_to={"role__in": ["nurse", "labtech"]},
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="staff_assignments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-assigned_at"],
                "unique_together": {("user", "company")},
            },
        ),
    ]
