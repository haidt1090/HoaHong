from django.db import migrations, models

import accounts.storage
import nationalsync.models


class Migration(migrations.Migration):

    dependencies = [
        ("nationalsync", "0004_syncjob_examination"),
    ]

    operations = [
        migrations.CreateModel(
            name="FacilitySignature",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "signature_image",
                    models.ImageField(
                        blank=True,
                        help_text=(
                            "Ảnh chữ ký PNG của bệnh viện. "
                            "Khi đồng bộ được chuyển thành base64."
                        ),
                        null=True,
                        storage=accounts.storage.PrivateSignatureStorage(),
                        upload_to=nationalsync.models.facility_signature_upload_to,
                    ),
                ),
                (
                    "signature_base64",
                    models.TextField(
                        blank=True,
                        help_text="Chữ ký bệnh viện dạng base64 khi không lưu file ảnh.",
                    ),
                ),
            ],
            options={
                "verbose_name": "Chữ ký bệnh viện",
                "verbose_name_plural": "Chữ ký bệnh viện",
            },
        ),
    ]
