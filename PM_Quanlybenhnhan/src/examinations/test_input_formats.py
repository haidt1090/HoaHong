"""Tests for DepartmentField.input_format (bp_slash)."""

from __future__ import annotations

from datetime import date

from django.test import SimpleTestCase, TestCase

from accounts.models import Company
from examinations.input_formats import apply_input_format, format_bp_slash
from examinations.models import (
    Department,
    DepartmentField,
    DepartmentResult,
    DepartmentTemplate,
    Examination,
    ExamPackage,
    ExamPackageDepartment,
)
from patients.models import Patient


class FormatBpSlashTests(SimpleTestCase):
    def test_five_digit_integer(self) -> None:
        self.assertEqual(format_bp_slash(11280), "112/80")
        self.assertEqual(format_bp_slash("11280"), "112/80")
        self.assertEqual(format_bp_slash(11280.0), "112/80")

    def test_four_digit_integer(self) -> None:
        self.assertEqual(format_bp_slash(1280), "12/80")
        self.assertEqual(format_bp_slash("1280"), "12/80")

    def test_existing_slash_is_kept(self) -> None:
        self.assertEqual(format_bp_slash("112/80"), "112/80")
        self.assertEqual(format_bp_slash("112 / 80"), "112/80")

    def test_other_lengths_left_alone(self) -> None:
        self.assertEqual(format_bp_slash("112"), "112")
        self.assertEqual(format_bp_slash("112800"), "112800")
        self.assertEqual(format_bp_slash(80), 80)

    def test_non_integer_float_left_alone(self) -> None:
        self.assertEqual(format_bp_slash(11280.5), 11280.5)

    def test_no_format_is_noop(self) -> None:
        self.assertEqual(apply_input_format("11280", None), "11280")
        self.assertEqual(apply_input_format("11280", {"key": "bp"}), "11280")
        self.assertEqual(
            apply_input_format("11280", {"key": "bp", "input_format": "bp_slash"}),
            "112/80",
        )


class InputFormatAsConfigTests(TestCase):
    def setUp(self) -> None:
        self.dept = Department.objects.get(code="xet_nghiem")
        self.tpl = DepartmentTemplate.objects.create(
            department=self.dept, name="Mẫu HA"
        )

    def test_as_config_omits_blank_input_format(self) -> None:
        field = DepartmentField.objects.create(
            template=self.tpl, key="note", label="Ghi chú", field_type="text"
        )
        self.assertNotIn("input_format", field.as_config())

    def test_as_config_includes_bp_slash(self) -> None:
        field = DepartmentField.objects.create(
            template=self.tpl,
            key="huyet_ap",
            label="Huyết áp",
            field_type="text",
            input_format="bp_slash",
        )
        self.assertEqual(field.as_config()["input_format"], "bp_slash")


class SyncValuesInputFormatTests(TestCase):
    def setUp(self) -> None:
        self.dept = Department.objects.get(code="xet_nghiem")
        self.tpl = DepartmentTemplate.objects.create(
            department=self.dept, name="Mẫu HA"
        )
        DepartmentField.objects.create(
            template=self.tpl,
            key="huyet_ap",
            label="Huyết áp",
            field_type="text",
            input_format="bp_slash",
        )
        company = Company.objects.create(name="Cty", code="CTY_BP")
        self.package = ExamPackage.objects.create(name="Gói", exam_type="periodic")
        ExamPackageDepartment.objects.create(
            exam_package=self.package,
            department=self.dept,
            template=self.tpl,
            order=1,
        )
        patient = Patient.objects.create(
            company=company,
            employee_code="E01",
            full_name="NV E01",
            dob=date.today(),
            gender="M",
        )
        exam = Examination.objects.create(
            patient=patient,
            exam_package=self.package,
            exam_type="periodic",
            exam_date=date.today(),
        )
        self.result = DepartmentResult.objects.create(
            examination=exam,
            department=self.dept,
            template=self.tpl,
            template_snapshot=self.tpl.fields_config,
        )

    def test_sync_formats_compact_digits(self) -> None:
        self.result._sync_values({"huyet_ap": "11280"}, randomize=False)
        self.assertEqual(self.result.data["huyet_ap"], "112/80")

    def test_sync_formats_excel_integer(self) -> None:
        self.result._sync_values({"huyet_ap": 11280}, randomize=False)
        self.assertEqual(self.result.data["huyet_ap"], "112/80")

    def test_import_formats_using_live_config(self) -> None:
        self.result.apply_imported_values(
            {"huyet_ap": 1280}, self.tpl.fields_config
        )
        self.assertEqual(self.result.data["huyet_ap"], "12/80")
