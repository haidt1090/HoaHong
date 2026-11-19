import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("nationalsync", "0006_sync_field_mapping"),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncMappingVersion",
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
                ("name", models.CharField(max_length=120)),
                ("is_default", models.BooleanField(default=False)),
                ("source_filename", models.CharField(blank=True, max_length=255)),
                ("extracted_fields", models.JSONField(blank=True, default=list)),
            ],
            options={
                "verbose_name": "Version mapping XML",
                "verbose_name_plural": "Version mapping XML",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="syncmappingversion",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_default=True),
                fields=("is_default",),
                name="unique_default_sync_mapping_version",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="syncfieldmapping",
            name="unique_sync_xml_tag",
        ),
        migrations.RemoveConstraint(
            model_name="syncfieldmapping",
            name="unique_sync_department_field_key",
        ),
        migrations.AddField(
            model_name="syncfieldmapping",
            name="version",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="mappings",
                to="nationalsync.syncmappingversion",
            ),
        ),
        migrations.AddConstraint(
            model_name="syncfieldmapping",
            constraint=models.UniqueConstraint(
                condition=~models.Q(xml_tag=""),
                fields=("version", "xml_tag"),
                name="unique_sync_xml_tag",
            ),
        ),
        migrations.AddConstraint(
            model_name="syncfieldmapping",
            constraint=models.UniqueConstraint(
                fields=("version", "department", "field_key"),
                name="unique_sync_department_field_key",
            ),
        ),
    ]
