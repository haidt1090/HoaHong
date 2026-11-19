import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0030_departmentfield_applies_to"),
        ("nationalsync", "0005_facility_signature"),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncFieldMapping",
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
                    "block",
                    models.CharField(
                        max_length=8,
                        choices=[
                            ("xml7", "XML7 — Khám lâm sàng"),
                            ("xml9", "XML9 — Tiền sử"),
                            ("xml10", "XML10 — Thể lực"),
                            ("xml11", "XML11 — Cận lâm sàng"),
                        ],
                    ),
                ),
                (
                    "xml_tag",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "Thẻ XML7/XML9/XML10, ví dụ CHIEU_CAO. "
                            "Để trống với cận lâm sàng."
                        ),
                        max_length=64,
                    ),
                ),
                (
                    "field_key",
                    models.CharField(
                        help_text="Khóa cột trên mẫu khoa (DepartmentField.key).",
                        max_length=100,
                    ),
                ),
                (
                    "alias_keys",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Khóa cũ vẫn còn trong lượt khám đã lưu.",
                    ),
                ),
                (
                    "ma_dich_vu",
                    models.CharField(
                        blank=True,
                        help_text="XML11 MA_DICH_VU.",
                        max_length=32,
                    ),
                ),
                (
                    "ma_chi_so",
                    models.CharField(
                        blank=True,
                        help_text="XML11 MA_CHI_SO.",
                        max_length=32,
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="sync_field_mappings",
                        to="examinations.department",
                    ),
                ),
            ],
            options={
                "verbose_name": "Mapping trường XML",
                "verbose_name_plural": "Mapping trường XML",
                "ordering": ["block", "xml_tag", "field_key"],
            },
        ),
        migrations.AddConstraint(
            model_name="syncfieldmapping",
            constraint=models.UniqueConstraint(
                condition=~models.Q(xml_tag=""),
                fields=("xml_tag",),
                name="unique_sync_xml_tag",
            ),
        ),
        migrations.AddConstraint(
            model_name="syncfieldmapping",
            constraint=models.UniqueConstraint(
                fields=("department", "field_key"),
                name="unique_sync_department_field_key",
            ),
        ),
    ]
