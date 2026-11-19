"""
Tests for Excel export functionality (Sprint 6).
"""
import io
from datetime import date

from openpyxl import load_workbook
from django.core.files.base import ContentFile
from django.test import TestCase
from openpyxl import load_workbook
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Company, CompanyExamPackage, User
from examinations.models import (
    Department,
    DepartmentField,
    DepartmentResult,
    DepartmentResultValue,
    DepartmentTemplate,
    Examination,
    ExamPackage,
    ExamPackageDepartment,
    ExportJob,
    _to_decimal,
    _value_as_text,
)
from patients.models import Patient


class ExportJobTests(TestCase):
    """Test Excel export API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="doctor@example.com",
            password="testpass123",
            role="doctor",
            full_name="Test Doctor",
        )
        self.client.force_authenticate(user=self.user)

        self.company = Company.objects.create(name="Test Company", code="TC001")

        self.department = Department.objects.create(
            name="Xét nghiệm máu",
            code="XNMAU",
            category="para_clinical",
        )

        self.template = DepartmentTemplate.objects.create(
            name="Template Xét nghiệm máu",
            department=self.department,
        )
        self.field1 = DepartmentField.objects.create(
            template=self.template,
            key="hemoglobin",
            label="Huyết sắc tố",
            field_type="number",
            unit="g/dL",
            normal_range_min=12.0,
            normal_range_max=16.0,
        )
        self.field2 = DepartmentField.objects.create(
            template=self.template,
            key="wbc",
            label="Bạch cầu",
            field_type="number",
            unit="G/L",
            normal_range_min=4.0,
            normal_range_max=10.0,
        )

        self.exam_package = ExamPackage.objects.create(
            name="Gói khám sức khỏe",
            exam_type="periodic",
        )
        ExamPackageDepartment.objects.create(
            exam_package=self.exam_package,
            department=self.department,
            template=self.template,
        )
        CompanyExamPackage.objects.create(
            company=self.company,
            exam_package=self.exam_package,
            pricing_mode="per_field",
            is_active=True,
        )

        self.patient1 = Patient.objects.create(
            employee_code="EMP001",
            full_name="Nguyễn Văn A",
            company=self.company,
            dob=date(1990, 1, 15),
            gender="M",
        )
        self.patient2 = Patient.objects.create(
            employee_code="EMP002",
            full_name="Trần Thị B",
            company=self.company,
            dob=date(1985, 5, 20),
            gender="F",
        )

        # Create examination with results for patient1
        self.examination = Examination.objects.create(
            patient=self.patient1,
            exam_package=self.exam_package,
            exam_date=date(2026, 7, 10),
            doctor=self.user,
        )
        self.dept_result = DepartmentResult.objects.create(
            examination=self.examination,
            department=self.department,
            template=self.template,
        )
        self._set_values(self.dept_result, {"hemoglobin": "14.5", "wbc": "7.2"})

    def _set_values(self, result, data):
        for k, v in data.items():
            DepartmentResultValue.objects.create(
                result=result,
                field_key=k,
                value_number=_to_decimal(v, "number"),
                value_text=_value_as_text(v, "number"),
            )

    def test_create_export_job_success(self):
        url = "/api/export/"
        data = {
            "company_id": str(self.company.id),
            "exam_package_id": str(self.exam_package.id),
            "department_id": str(self.department.id),
            "exam_date": "2026-07-10",
        }
        response = self.client.post(url, data, format="json")
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertIn("id", response.data)
        self.assertIn("status", response.data)
        self.assertIn("progress", response.data)

    def test_create_export_job_missing_company(self):
        url = "/api/export/"
        data = {
            "exam_package_id": str(self.exam_package.id),
            "department_id": str(self.department.id),
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("company_id", str(response.data))

    def test_create_export_job_missing_department(self):
        url = "/api/export/"
        data = {
            "company_id": str(self.company.id),
            "exam_package_id": str(self.exam_package.id),
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("department_id", str(response.data))

    def test_retrieve_export_job(self):
        export_job = ExportJob.objects.create(
            company=self.company,
            exam_package=self.exam_package,
            department=self.department,
            created_by=self.user,
            status="completed",
            current_progress=10,
            total_progress=10,
        )
        url = f"/api/export/{export_job.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(export_job.id))
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["progress"]["current"], 10)

    def test_download_export_job_completed(self):
        export_job = ExportJob.objects.create(
            company=self.company,
            exam_package=self.exam_package,
            department=self.department,
            created_by=self.user,
            status="completed",
        )
        export_job.file.save("test_export.xlsx", ContentFile(b"dummy excel content"))
        url = f"/api/export/{export_job.id}/download/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("application/vnd.openxmlformats", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])

    def test_download_export_job_not_completed(self):
        export_job = ExportJob.objects.create(
            company=self.company,
            exam_package=self.exam_package,
            department=self.department,
            created_by=self.user,
            status="processing",
        )
        url = f"/api/export/{export_job.id}/download/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", str(response.data))

    def test_list_export_jobs(self):
        ExportJob.objects.create(
            company=self.company,
            exam_package=self.exam_package,
            department=self.department,
            created_by=self.user,
            status="completed",
        )
        ExportJob.objects.create(
            company=self.company,
            exam_package=self.exam_package,
            department=self.department,
            created_by=self.user,
            status="pending",
        )
        url = "/api/export/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 2)

    def test_export_job_permission_denied(self):
        patient_user = User.objects.create_user(
            email="patient@example.com",
            password="testpass123",
            role="patient",
            full_name="Test Patient",
        )
        self.client.force_authenticate(user=patient_user)
        url = "/api/export/"
        data = {
            "company_id": str(self.company.id),
            "exam_package_id": str(self.exam_package.id),
            "department_id": str(self.department.id),
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_fills_package_results_without_exam_date(self):
        """Export is scoped by the active company package, not calendar date."""
        response = self.client.post(
            "/api/export/",
            {
                "company_id": str(self.company.id),
                "package_id": str(self.exam_package.id),
                "department_id": str(self.department.id),
            },
            format="json",
        )
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED]
        )
        self.assertEqual(response.data["status"], "completed")
        self.assertIsNone(response.data.get("exam_date"))

        download = self.client.get(f"/api/export/{response.data['id']}/download/")
        self.assertEqual(download.status_code, status.HTTP_200_OK)
        ws = load_workbook(io.BytesIO(download.content)).active
        self.assertEqual(ws.cell(1, 1).value, "Mã NV")
        self.assertEqual(ws.cell(1, 3).value, "Huyết sắc tố")
        self.assertEqual(ws.cell(3, 1).value, "EMP001")
        self.assertEqual(ws.cell(3, 3).value, 14.5)
        self.assertEqual(ws.cell(3, 4).value, 7.2)
        self.assertEqual(ws.cell(4, 1).value, "EMP002")
        self.assertIn(ws.cell(4, 3).value, (None, ""))

    def test_export_ignores_mismatched_exam_date(self):
        """Sending a date that is not the exam's date still exports package data."""
        response = self.client.post(
            "/api/export/",
            {
                "company_id": str(self.company.id),
                "package_id": str(self.exam_package.id),
                "department_id": str(self.department.id),
                "exam_date": "2099-01-01",
            },
            format="json",
        )
        self.assertEqual(response.data["status"], "completed")
        download = self.client.get(f"/api/export/{response.data['id']}/download/")
        ws = load_workbook(io.BytesIO(download.content)).active
        self.assertEqual(ws.cell(3, 1).value, "EMP001")
        self.assertEqual(ws.cell(3, 3).value, 14.5)

    def test_export_rejects_inactive_company_package(self):
        CompanyExamPackage.objects.filter(
            company=self.company, exam_package=self.exam_package
        ).update(is_active=False)
        response = self.client.post(
            "/api/export/",
            {
                "company_id": str(self.company.id),
                "package_id": str(self.exam_package.id),
                "department_id": str(self.department.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("package_id", response.data)
