from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0027_add_gender_overrides"),
    ]

    operations = [
        migrations.AddField(
            model_name="departmentfield",
            name="input_format",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "—"),
                    ("bp_slash", "Huyết áp (11280 → 112/80)"),
                ],
                default="",
                help_text=(
                    "Định dạng nhập liệu (không phụ thuộc key). "
                    "bp_slash: số nguyên 4–5 chữ số → chèn / trước 2 số cuối "
                    "(11280 → 112/80). Áp dụng khi rời ô và khi import Excel."
                ),
                max_length=32,
            ),
        ),
    ]
