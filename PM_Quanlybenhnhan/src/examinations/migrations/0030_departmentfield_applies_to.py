# Generated manually for DepartmentField.applies_to

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0029_alter_departmentfield_gender_overrides"),
    ]

    operations = [
        migrations.AddField(
            model_name="departmentfield",
            name="applies_to",
            field=models.CharField(
                choices=[
                    ("all", "Tất cả"),
                    ("M", "Nam"),
                    ("F", "Nữ"),
                ],
                default="all",
                help_text=(
                    "Giới tính được áp dụng. 'Nữ' = không seed/không bắt buộc "
                    "với nam (ví dụ siêu âm bụng). 'Nam' tương tự cho nữ."
                ),
                max_length=8,
            ),
        ),
    ]
