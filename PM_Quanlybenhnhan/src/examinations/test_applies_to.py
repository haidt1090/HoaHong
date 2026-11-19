"""Tests for DepartmentField.applies_to (gender-scoped fields)."""

from __future__ import annotations

from datetime import date

from django.test import SimpleTestCase, TestCase

from accounts.models import Company
from examinations.field_scope import (
    field_applies_to_gender,
    should_seed_field,
)
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


class FieldScopeHelperTests(SimpleTestCase):
    def test_all_applies_to_everyone(self) -> None:
        field = {"applies_to": "all"}
        self.assertTrue(field_applies_to_gender(field, "M"))
        self.assertTrue(field_applies_to_gender(field, "F"))
        self.assertTrue(should_seed_field(field, "M"))
        self.assertTrue(should_seed_field(field, None))

    def test_female_only_hides_for_male(self) -> None:
        field = {"applies_to": "F"}
        self.assertFalse(field_applies_to_gender(field, "M"))
        self.assertTrue(field_applies_to_gender(field, "F"))
        self.assertTrue(field_applies_to_gender(field, None))
        self.assertFalse(should_seed_field(field, "M"))
        self.assertTrue(should_seed_field(field, "F"))
        self.assertFalse(should_seed_field(field, None))

    def test_missing_applies_to_is_all(self) -> None:
        self.assertTrue(should_seed_field({"key": "x"}, "M"))


class AppliesToAsConfigTests(TestCase):
    def setUp(self) -> None:
        self.dept = Department.objects.get(code="sieu_am")
        self.tpl = DepartmentTemplate.objects.create(
            department=self.dept, name="Mẫu SA"
        )

    def test_as_config_omits_all(self) -> None:
        field = DepartmentField.objects.create(
            template=self.tpl, key="note", label="Ghi chú", field_type="text"
        )
        self.assertNotIn("applies_to", field.as_config())

    def test_as_config_includes_female(self) -> None:
        field = DepartmentField.objects.create(
            template=self.tpl,
            key="sa_bung",
            label="Siêu âm bụng",
            field_type="text",
            applies_to="F",
            default_value="Bình thường",
        )
        self.assertEqual(field.as_config()["applies_to"], "F")


class AppliesToSeedTests(TestCase):
    def setUp(self) -> None:
        self.dept = Department.objects.get(code="sieu_am")
        self.tpl = DepartmentTemplate.objects.create(
            department=self.dept, name="Mẫu SA"
        )
        DepartmentField.objects.create(
            template=self.tpl,
            key="sa_bung",
            label="Siêu âm bụng",
            field_type="text",
            applies_to="F",
            default_value="Bình thường",
        )
        DepartmentField.objects.create(
            template=self.tpl,
            key="sa_gan",
            label="Siêu âm gan",
            field_type="text",
            default_value="Bình thường",
        )
        company = Company.objects.create(name="Cty", code="CTY_SA")
        self.package = ExamPackage.objects.create(name="Gói", exam_type="periodic")
        ExamPackageDepartment.objects.create(
            exam_package=self.package,
            department=self.dept,
            template=self.tpl,
            order=1,
        )
        self.company = company

    def _result(self, gender: str | None) -> DepartmentResult:
        patient = Patient.objects.create(
            company=self.company,
            employee_code=f"E-{gender or 'X'}",
            full_name="NV",
            dob=date.today(),
            gender=gender,
        )
        exam = Examination.objects.create(
            patient=patient,
            exam_package=self.package,
            exam_type="periodic",
            exam_date=date.today(),
        )
        return DepartmentResult.objects.create(
            examination=exam,
            department=self.dept,
            template=self.tpl,
            template_snapshot=self.tpl.fields_config,
        )

    def test_male_does_not_get_female_only_default(self) -> None:
        result = self._result("M")
        result._sync_values({}, randomize=True)
        self.assertNotIn("sa_bung", result.data)
        self.assertEqual(result.data["sa_gan"], "Bình thường")

    def test_female_gets_female_only_default(self) -> None:
        result = self._result("F")
        result._sync_values({}, randomize=True)
        self.assertEqual(result.data["sa_bung"], "Bình thường")
        self.assertEqual(result.data["sa_gan"], "Bình thường")

    def test_unknown_gender_does_not_seed_restricted_field(self) -> None:
        result = self._result(None)
        result._sync_values({}, randomize=True)
        self.assertNotIn("sa_bung", result.data)
        self.assertEqual(result.data["sa_gan"], "Bình thường")


class AppliesToCompletenessTests(TestCase):
    def setUp(self) -> None:
        self.dept = Department.objects.get(code="sieu_am")
        self.tpl = DepartmentTemplate.objects.create(
            department=self.dept, name="Mẫu SA"
        )
        DepartmentField.objects.create(
            template=self.tpl,
            key="sa_bung",
            label="Siêu âm bụng",
            field_type="text",
            applies_to="F",
            required=True,
        )
        DepartmentField.objects.create(
            template=self.tpl,
            key="sa_gan",
            label="Siêu âm gan",
            field_type="text",
        )
        company = Company.objects.create(name="Cty", code="CTY_SA2")
        self.package = ExamPackage.objects.create(name="Gói", exam_type="periodic")
        ExamPackageDepartment.objects.create(
            exam_package=self.package,
            department=self.dept,
            template=self.tpl,
            order=1,
        )
        self.company = company

    def _exam(self, gender: str) -> Examination:
        patient = Patient.objects.create(
            company=self.company,
            employee_code=f"C-{gender}",
            full_name="NV",
            dob=date.today(),
            gender=gender,
        )
        exam = Examination.objects.create(
            patient=patient,
            exam_package=self.package,
            exam_type="periodic",
            exam_date=date.today(),
        )
        DepartmentResult.objects.create(
            examination=exam,
            department=self.dept,
            template=self.tpl,
            template_snapshot=self.tpl.fields_config,
        )
        return exam

    def test_male_complete_without_female_only_field(self) -> None:
        exam = self._exam("M")
        result = exam.department_results.get()
        result._sync_values({"sa_gan": "BT"}, randomize=False)
        self.assertTrue(exam.all_departments_filled())

    def test_female_incomplete_without_female_only_field(self) -> None:
        exam = self._exam("F")
        result = exam.department_results.get()
        result._sync_values({"sa_gan": "BT"}, randomize=False)
        self.assertFalse(exam.all_departments_filled())
