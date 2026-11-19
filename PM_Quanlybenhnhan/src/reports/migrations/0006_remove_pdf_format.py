# Generated manually — remove PDF from report output format

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0005_employeeexamreport"),
    ]

    operations = [
        migrations.AlterField(
            model_name="report",
            name="output_format",
            field=models.CharField(
                choices=[("xlsx", "Excel"), ("html", "HTML")],
                default="xlsx",
                max_length=5,
            ),
        ),
    ]
