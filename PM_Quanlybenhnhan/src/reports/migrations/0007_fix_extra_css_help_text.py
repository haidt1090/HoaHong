# Generated manually — fix help_text containing literal <style> tag that
# broke the admin change form (rendered via |safe).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0006_remove_pdf_format"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reporttemplate",
            name="extra_css",
            field=models.TextField(
                blank=True,
                help_text="CSS bổ sung, chèn vào thẻ style của tài liệu.",
            ),
        ),
    ]
