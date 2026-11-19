"""
Tests for the scheduled diagnosis scan (Sprint 7).

Covers:
  * _is_unconcluded gating (never overwrite doctor data)
  * _apply_diagnosis filling work_fitness/disease/consultation
  * scan_diagnosis_task end-to-end
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounts.models import Company, CompanyExamPackage
from diagnosis.models import DiagnosisKeyword
from diagnosis.tasks import _apply_diagnosis, _is_unconcluded, scan_diagnosis_task
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


class DiagnosisScanTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.company = Company.objects.create(name="Cty", code="SCAN")
        cls.patient = Patient.objects.create(
            company=cls.company, employee_code="E1", full_name="Nguyễn Văn A"
        )
        cls.dept = Department.objects.create(name="Xét nghiệm", code="XN")
        cls.template = DepartmentTemplate.objects.create(
            department=cls.dept, name="XN máu"
        )
        # A numeric field with an abnormal definition for "high".
        cls.field = DepartmentField.objects.create(
            template=cls.template,
            key="men_gan",
            label="Men gan",
            field_type="number",
            normal_range_min=Decimal("0"),
            normal_range_max=Decimal("40"),
            order=0,
        )
        cls.package = ExamPackage.objects.create(name="KSK", exam_type="periodic")
        ExamPackageDepartment.objects.create(
            exam_package=cls.package, department=cls.dept, template=cls.template
        )
        cls.cep = CompanyExamPackage.objects.create(
            company=cls.company, exam_package=cls.package, pricing_mode="per_field"
        )

        cls.keyword = DiagnosisKeyword.objects.create(
            keyword="tăng men gan",
            disease_name="Bệnh gan",
            conclusion_template="Tư vấn mẫu",
            classification=DiagnosisKeyword.CLASSIFICATION_UNFIT,
            is_active=True,
        )

    def _make_exam(self, **kwargs) -> Examination:
        return Examination.objects.create(
            patient=self.patient,
            company_exam_package=self.cep,
            exam_package=self.package,
            exam_type="periodic",
            exam_date=date(2026, 1, 1),
            status="completed",
            **kwargs,
        )

    def _add_result(self, exam: Examination, data: dict) -> None:
        result = DepartmentResult.objects.create(
            examination=exam,
            department=self.dept,
            template=self.template,
            template_snapshot=[
                {
                    "key": "men_gan",
                    "label": "Men gan",
                    "type": "number",
                    "normal_range": {"min": 0, "max": 40},
                    "abnormal_definitions": [
                        {"direction": "high", "label": "Tăng men gan"}
                    ],
                }
            ],
        )
        result._sync_values(data)
        # DepartmentResult.save() recomputes exam status before values sync,
        # so force it back to completed for the scan to pick it up.
        exam.status = Examination.STATUS_COMPLETED
        exam.save(update_fields=["status"])

    def test_is_unconcluded_gates_correctly(self):
        exam = self._make_exam()
        self.assertTrue(_is_unconcluded(exam))

        exam.work_fitness = "fit"
        exam.save()
        self.assertFalse(_is_unconcluded(exam))

    def test_is_unconcluded_never_overwrites_consultation(self):
        exam = self._make_exam(consultation="Đã có tư vấn")
        self.assertFalse(_is_unconcluded(exam))

    def test_apply_diagnosis_fills_fields(self):
        exam = self._make_exam()
        self._add_result(exam, {"men_gan": 90})

        changed = _apply_diagnosis(exam)
        self.assertTrue(changed)
        exam.refresh_from_db()
        self.assertEqual(exam.work_fitness, "unfit")
        self.assertIn("Bệnh gan", exam.disease)
        self.assertIn("Tư vấn mẫu", exam.consultation)
        self.assertTrue(exam.auto_diagnosed)

    def test_apply_diagnosis_no_match_marks_fit(self):
        exam = self._make_exam()
        self._add_result(exam, {"men_gan": 20})  # within normal range
        changed = _apply_diagnosis(exam)
        self.assertTrue(changed)
        exam.refresh_from_db()
        self.assertEqual(exam.work_fitness, "fit")
        self.assertEqual(exam.disease, "")
        self.assertTrue(exam.auto_diagnosed)

    def test_scan_task_end_to_end(self):
        exam = self._make_exam()
        self._add_result(exam, {"men_gan": 90})
        result = scan_diagnosis_task(limit=50)
        self.assertGreaterEqual(result["filled"], 1)
        exam.refresh_from_db()
        self.assertEqual(exam.work_fitness, "unfit")
        self.assertTrue(exam.auto_diagnosed)

    def test_scan_skips_already_concluded(self):
        exam = self._make_exam(work_fitness="fit")
        self._add_result(exam, {"men_gan": 90})
        result = scan_diagnosis_task(limit=50)
        self.assertEqual(result["filled"], 0)
        exam.refresh_from_db()
        self.assertEqual(exam.work_fitness, "fit")
        self.assertEqual(exam.disease, "")
