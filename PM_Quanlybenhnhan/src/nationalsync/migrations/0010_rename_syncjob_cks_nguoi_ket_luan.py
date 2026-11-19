from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("nationalsync", "0009_syncjob_cks_benh_vien"),
    ]

    operations = [
        migrations.RenameField(
            model_name="syncjob",
            old_name="cks_benh_vien",
            new_name="cks_nguoi_ket_luan",
        ),
    ]
