"""Employee Excel import creates seeded examinations for active company packages."""

from __future__ import annotations

import io
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Company, CompanyExamPackage
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
from patients.tests import _make_user


def _xlsx(rows: list[list]) -> SimpleUploadedFile:
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "STT",
            "Bộ phận",
            "Mã NV",
            "Họ và tên",
            "Giới tính",
            "Ngày sinh",
        ]
    )
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return SimpleUploadedFile(
        "employees.xlsx",
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


class EmployeeImportCreatesExaminationTests(APITestCase):
    def setUp(self) -> None:
        self.admin = _make_user("admin", email="admin@import-exam.test")
        self.client.force_authenticate(self.admin)
        self.company = Company.objects.create(name="Cty Import", code="IMP_EX")
        self.department = Department.objects.get(code="xet_nghiem")
        self.template = DepartmentTemplate.objects.create(
            department=self.department, name="XN import"
        )
        DepartmentField.objects.create(
            template=self.template,
            key="hemoglobin",
            label="Huyết sắc tố",
            field_type="number",
            normal_range_min=12,
            normal_range_max=16,
            default_value="",
            order=1,
        )
        DepartmentField.objects.create(
            template=self.template,
            key="note",
            label="Ghi chú",
            field_type="text",
            default_value="BT",
            order=2,
        )
        self.package = ExamPackage.objects.create(
            name="Gói định kỳ", exam_type="periodic", is_active=True
        )
        ExamPackageDepartment.objects.create(
            exam_package=self.package,
            department=self.department,
            template=self.template,
            order=1,
        )
        self.url = reverse("patients:patient-import-excel")

    def _post(self, rows: list[list], company_id: str | None = None):
        return self.client.post(
            self.url,
            {"file": _xlsx(rows), "company_id": company_id or str(self.company.id)},
            format="multipart",
        )

    def test_no_active_package_creates_patient_only(self) -> None:
        response = self._post([[1, "HC", "NV100", "Nguyễn Văn A", "Nam", "1990-01-01"]])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(response.data["examinations_created"], 0)
        self.assertEqual(Patient.objects.filter(company=self.company).count(), 1)
        self.assertEqual(Examination.objects.count(), 0)

    def test_active_package_creates_exam_and_seeds_values(self) -> None:
        CompanyExamPackage.objects.create(
            company=self.company,
            exam_package=self.package,
            pricing_mode="package_total",
            is_active=True,
        )
        response = self._post([[1, "HC", "NV101", "Trần Thị B", "Nữ", "1991-02-02"]])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(response.data["examinations_created"], 1)

        patient = Patient.objects.get(company=self.company, employee_code="NV101")
        exam = Examination.objects.get(patient=patient)
        self.assertEqual(exam.exam_package_id, self.package.id)
        self.assertEqual(exam.exam_type, "periodic")
        self.assertEqual(exam.exam_date, timezone.localdate())

        result = DepartmentResult.objects.get(examination=exam, department=self.department)
        data = result.data
        self.assertEqual(data.get("note"), "BT")
        hb = float(data["hemoglobin"])
        self.assertGreaterEqual(hb, 12.0)
        self.assertLessEqual(hb, 16.0)

    def test_inactive_package_is_skipped(self) -> None:
        CompanyExamPackage.objects.create(
            company=self.company,
            exam_package=self.package,
            pricing_mode="package_total",
            is_active=False,
        )
        response = self._post([[1, "HC", "NV102", "Lê C", "Nam", "1992-03-03"]])
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(response.data["examinations_created"], 0)
        self.assertEqual(Examination.objects.count(), 0)

    def test_two_active_packages_create_two_exams(self) -> None:
        pkg2 = ExamPackage.objects.create(
            name="Gói nghề nghiệp", exam_type="occupational", is_active=True
        )
        ExamPackageDepartment.objects.create(
            exam_package=pkg2,
            department=self.department,
            template=self.template,
            order=1,
        )
        CompanyExamPackage.objects.create(
            company=self.company,
            exam_package=self.package,
            pricing_mode="package_total",
            is_active=True,
        )
        CompanyExamPackage.objects.create(
            company=self.company,
            exam_package=pkg2,
            pricing_mode="package_total",
            is_active=True,
        )
        response = self._post([[1, "HC", "NV103", "Phạm D", "Nam", "1993-04-04"]])
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(response.data["examinations_created"], 2)
        patient = Patient.objects.get(employee_code="NV103")
        self.assertEqual(Examination.objects.filter(patient=patient).count(), 2)
