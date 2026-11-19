from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("nationalsync", "0008_syncjob_exam_stats"),
    ]

    operations = [
        migrations.AddField(
            model_name="syncjob",
            name="cks_benh_vien",
            field=models.TextField(
                blank=True,
                help_text="CMS/PKCS#7 Base64 from the USB token, written into CKS_BENH_VIEN.",
            ),
        ),
    ]
