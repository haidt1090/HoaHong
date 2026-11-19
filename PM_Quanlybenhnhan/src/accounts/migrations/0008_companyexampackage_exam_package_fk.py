"""Replace CompanyExamPackage.exam_package_id placeholder with a real FK.

Sprint 4 wires CompanyExamPackage to examinations.ExamPackage. The old
``exam_package_id`` UUID placeholder held no real references (Sprint 3 stub),
so it is dropped and replaced by a ForeignKey.
"""

from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


def clear_stub_rows(apps, schema_editor):
    """Old rows referenced placeholder UUIDs, not real packages — drop them."""
    CompanyExamPackage = apps.get_model("accounts", "CompanyExamPackage")
    CompanyExamPackage.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_companyexampackage"),
        ("examinations", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(clear_stub_rows, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="companyexampackage",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="companyexampackage",
            name="exam_package_id",
        ),
        migrations.AddField(
            model_name="companyexampackage",
            name="exam_package",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="company_packages",
                to="examinations.exampackage",
            ),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name="companyexampackage",
            unique_together={("company", "exam_package")},
        ),
    ]
