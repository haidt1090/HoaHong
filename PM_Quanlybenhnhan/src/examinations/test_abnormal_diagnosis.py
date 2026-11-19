"""
Tests for DepartmentFieldAbnormal model and abnormal-aware findings aggregation.
"""
from datetime import date
from django.test import TestCase
from examinations.models import (
    Department,
    DepartmentField,
    DepartmentFieldAbnormal,
    DepartmentResult,
    DepartmentTemplate,
    Examination,
    ExamPackage,
    ExamPackageDepartment,
)
from patients.models import Patient
from accounts.models import User, Company


class DepartmentFieldAbnormalModelTests(TestCase):
    """Test the DepartmentFieldAbnormal model."""

    def setUp(self):
        self.dept = Department.objects.create(name="Xét nghiệm", code="XN_TEST", category="para_clinical")
        self.template = DepartmentTemplate.objects.create(name="Template test", department=self.dept)
        self.field = DepartmentField.objects.create(
            template=self.template, key="hr", label="Nhịp tim",
            field_type="number", normal_range_min=60.0, normal_range_max=135.0,
        )

    def test_create_abnormal_definition(self):
        abnormal = DepartmentFieldAbnormal.objects.create(
            field=self.field, direction="low", label="Nhịp tim chậm",
        )
        self.assertEqual(abnormal.field, self.field)
        self.assertEqual(abnormal.label, "Nhịp tim chậm")

    def test_unique_per_field_direction(self):
        DepartmentFieldAbnormal.objects.create(
            field=self.field, direction="low", label="Thấp",
        )
        with self.assertRaises(Exception):
            DepartmentFieldAbnormal.objects.create(
                field=self.field, direction="low", label="Rất thấp",
            )

    def test_as_config_includes_abnormal_definitions(self):
        DepartmentFieldAbnormal.objects.create(
            field=self.field, direction="low", label="Nhịp tim chậm",
        )
        DepartmentFieldAbnormal.objects.create(
            field=self.field, direction="high", label="Nhịp tim nhanh",
        )
        cfg = self.field.as_config()
        self.assertIn("abnormal_definitions", cfg)
        self.assertEqual(len(cfg["abnormal_definitions"]), 2)
        directions = {ad["direction"] for ad in cfg["abnormal_definitions"]}
        self.assertEqual(directions, {"low", "high"})


class AggregateFindingsTests(TestCase):
    """Test the aggregate_findings function with abnormal detection."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="doctor@test.com", password="pass", role="doctor", full_name="Dr Test",
        )
        self.company = Company.objects.create(name="Test Co", code="TC")
        self.patient = Patient.objects.create(
            company=self.company, employee_code="NV001", full_name="Test Patient",
            dob=date(1990, 1, 1), gender="M",
        )

        self.dept = Department.objects.create(name="Xét nghiệm", code="XN_FIND", category="para_clinical")
        self.template = DepartmentTemplate.objects.create(name="Template test", department=self.dept)

        # Field with abnormal definitions
        self.hr_field = DepartmentField.objects.create(
            template=self.template, key="hr", label="Nhịp tim",
            field_type="number", normal_range_min=60.0, normal_range_max=135.0,
        )
        DepartmentFieldAbnormal.objects.create(
            field=self.hr_field, direction="low", label="Nhịp tim chậm",
        )
        DepartmentFieldAbnormal.objects.create(
            field=self.hr_field, direction="high", label="Nhịp tim nhanh",
        )

        # Field without abnormal definitions
        self.hb_field = DepartmentField.objects.create(
            template=self.template, key="hb", label="Huyết sắc tố",
            field_type="number", normal_range_min=12.0, normal_range_max=16.0,
        )

        # Text field
        self.note_field = DepartmentField.objects.create(
            template=self.template, key="note", label="Ghi chú",
            field_type="textarea",
        )

        # Exam
        self.exam_pkg = ExamPackage.objects.create(name="Gói test", exam_type="periodic")
        ExamPackageDepartment.objects.create(
            exam_package=self.exam_pkg, department=self.dept, template=self.template,
        )
        self.exam = Examination.objects.create(
            patient=self.patient, exam_package=self.exam_pkg,
            exam_date=date.today(), doctor=self.user, exam_type="periodic",
        )

    def _create_dept_result(self, data):
        dr = DepartmentResult.objects.create(
            examination=self.exam, department=self.dept,
            template=self.template, template_snapshot=self.template.fields_config,
        )
        dr._sync_values(data)
        return dr

    def test_low_value_shows_abnormal_label(self):
        from diagnosis.services import aggregate_findings
        self._create_dept_result({"hr": 52, "hb": 14.5})
        result = aggregate_findings(self.exam)
        self.assertIn("Nhịp tim chậm", result)
        self.assertNotIn("Nhịp tim: 52", result)

    def test_high_value_shows_abnormal_label(self):
        from diagnosis.services import aggregate_findings
        self._create_dept_result({"hr": 150, "hb": 15.0})
        result = aggregate_findings(self.exam)
        self.assertIn("Nhịp tim nhanh", result)
        self.assertNotIn("Nhịp tim: 150", result)

    def test_normal_value_is_skipped(self):
        """Values within normal_range are skipped entirely."""
        from diagnosis.services import aggregate_findings
        self._create_dept_result({"hr": 80, "hb": 14.0})
        result = aggregate_findings(self.exam)
        self.assertNotIn("Nhịp tim: 80", result)
        self.assertNotIn("Huyết sắc tố: 14.0", result)
        self.assertEqual(result, "")

    def test_text_field_uses_raw_value(self):
        from diagnosis.services import aggregate_findings
        self._create_dept_result({"note": "Á sừng da đầu"})
        result = aggregate_findings(self.exam)
        self.assertIn("Ghi chú: Á sừng da đầu", result)
