# Generated manually for P3-S7

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0019_change_disease_to_m2m"),
    ]

    operations = [
        migrations.AddField(
            model_name="examination",
            name="consultation",
            field=models.TextField(
                blank=True,
                help_text="Tư vấn từ kết quả chẩn đoán",
            ),
        ),
    ]
