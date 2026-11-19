# Generated manually — per-exam sync success / skip tracking.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("nationalsync", "0007_sync_mapping_version"),
    ]

    operations = [
        migrations.AddField(
            model_name="syncjob",
            name="failed_count",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Số lượt khám đẩy thất bại trong job này.",
            ),
        ),
        migrations.AddField(
            model_name="syncjob",
            name="skipped_count",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Số lượt đã đồng bộ thành công trước đó (bỏ qua khi sync tất cả).",
            ),
        ),
        migrations.AddField(
            model_name="syncjob",
            name="success_count",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Số lượt khám đẩy thành công trong job này.",
            ),
        ),
        migrations.AddField(
            model_name="syncjob",
            name="synced_examination_ids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="UUID các lượt khám đẩy thành công (để bỏ qua lần sau).",
            ),
        ),
    ]
