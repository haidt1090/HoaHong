# Generated manually — add cache_version to invalidate stale cached HTML.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0007_fix_extra_css_help_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="employeeexamreport",
            name="cache_version",
            field=models.IntegerField(
                default=0,
                help_text="Bumped when rendering logic changes, to invalidate cached HTML.",
            ),
        ),
    ]
