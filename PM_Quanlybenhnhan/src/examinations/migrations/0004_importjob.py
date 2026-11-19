"""
Sprint 6 — Add ImportJob model for per-department Excel import tracking.
"""

from __future__ import annotations

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0003_examination_departmentresult_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ImportJob",
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
                (
                    "exam_date",
                    models.DateField(
                        help_text="Ngày khám áp dụng cho tất cả bệnh nhân trong file"
                    ),
                ),
                ("file", models.FileField(upload_to="imports/%Y/%m/%d/")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Chờ xử lý"),
                            ("processing", "Đang xử lý"),
                            ("completed", "Hoàn thành"),
                            ("failed", "Thất bại"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("total_rows", models.PositiveIntegerField(default=0)),
                ("success_count", models.PositiveIntegerField(default=0)),
                ("updated_count", models.PositiveIntegerField(default=0)),
                ("skipped_count", models.PositiveIntegerField(default=0)),
                (
                    "errors",
                    models.JSONField(
                        default=list,
                        help_text="List of error dicts: {row, employee_code, message}",
                    ),
                ),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="import_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="import_jobs",
                        to="examinations.department",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="importjob",
            index=models.Index(fields=["status"], name="examinatio_importj_status_idx"),
        ),
        migrations.AddIndex(
            model_name="importjob",
            index=models.Index(
                fields=["department", "exam_date"],
                name="examinatio_importj_dept_date_idx",
            ),
        ),
    ]
