# Generated manually for Excel letterhead fields on ReportTemplate

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0008_employeeexamreport_cache_version"),
    ]

    operations = [
        migrations.AddField(
            model_name="reporttemplate",
            name="header_xlsx",
            field=models.FileField(
                blank=True,
                help_text="File Excel (.xlsx) đầu trang — giữ nguyên format/style khi ghép vào báo cáo.",
                null=True,
                upload_to="report_templates/headers/",
            ),
        ),
        migrations.AddField(
            model_name="reporttemplate",
            name="footer_xlsx",
            field=models.FileField(
                blank=True,
                help_text="File Excel (.xlsx) chân trang — giữ nguyên format/style khi ghép vào báo cáo.",
                null=True,
                upload_to="report_templates/footers/",
            ),
        ),
        migrations.RemoveField(
            model_name="reporttemplate",
            name="header_html",
        ),
        migrations.RemoveField(
            model_name="reporttemplate",
            name="footer_html",
        ),
    ]
