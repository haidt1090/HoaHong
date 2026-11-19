"""
Tests for Sprint 6 — Per-department Excel import and template download.
"""

from __future__ import annotations

import io
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Company, User
from examinations.excel_utils import (
    generate_department_template,
    parse_department_import,
)
from examinations.models import (
    Department,
    DepartmentField,
    DepartmentResult,
    DepartmentTemplate,
    Examination,
    ExamPackage,
    ExamPackageDepartment,
    ImportJob,
)
from patients.models import Patient


def _resolve_nr(entry, key):
    nr = entry.get("normal_range")
    if isinstance(nr, dict):
        return nr.get(key)
    return entry.get(f"normal_range_{key}")


def _create_template(dept, name, entries):
    """Create a template with DepartmentField rows from config entries."""
    tpl = DepartmentTemplate.objects.create(department=dept, name=name)
    DepartmentField.objects.bulk_create(
        [
            DepartmentField(
                template=tpl,
                key=e["key"],
                label=e["label"],
                field_type=e.get("field_type", e.get("type", "text")),
                unit=e.get("unit", ""),
                required=e.get("required", False),
                order=e.get("order", 0),
                normal_range_min=_resolve_nr(e, "min"),
                normal_range_max=_resolve_nr(e, "max"),
                default_value=e.get("default_value", ""),
                default_price=e.get("default_price", 0),
                test_category=e.get("test_category", ""),
                options=e.get("options", []),
            )
            for e in entries
        ]
    )
    return tpl


class ExcelTemplateGenerationTest(TestCase):
    """Test Excel template generation from DepartmentTemplate."""

    def setUp(self) -> None:
        self.department = Department.objects.create(
            name="Xét nghiệm máu",
            code="xet_nghiem_mau",
            category="para_clinical",
        )
        self.template = _create_template(
            self.department,
            "Template XN máu",
            [
                {
                    "key": "hemoglobin",
                    "label": "Huyết sắc tố",
                    "type": "number",
                    "unit": "g/dL",
                    "normal_range": {"min": 12.0, "max": 16.0},
                    "required": True,
                },
                {
                    "key": "alt",
                    "label": "ALT (SGOT)",
                    "type": "number",
                    "unit": "U/L",
                    "normal_range": {"min": 0, "max": 40},
                    "required": False,
                },
                {
                    "key": "gender",
                    "label": "Giới tính",
                    "type": "select",
                    "options": ["Nam", "Nữ"],
                    "required": False,
                },
            ],
        )

    def test_generate_template_creates_valid_xlsx(self) -> None:
        """Template generation produces a valid .xlsx file."""
        content = generate_department_template(
            department_name=self.department.name,
            fields_config=self.template.fields_config,
        )
        self.assertIsInstance(content, bytes)
        self.assertGreater(len(content), 0)

    def test_template_has_employee_code_column(self) -> None:
        """Template includes employee_code as first column."""
        content = generate_department_template(
            department_name=self.department.name,
            fields_config=self.template.fields_config,
        )
        # Parse the generated file
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(content))
        ws = wb.active
        # First cell should be employee_code
        self.assertEqual(ws.cell(row=1, column=1).value, "employee_code")
        # Second row should have Vietnamese label
        self.assertEqual(ws.cell(row=2, column=1).value, "Mã nhân viên")
        wb.close()


class ExcelImportParsingTest(TestCase):
    """Test Excel file parsing for import."""

    def setUp(self) -> None:
        self.fields_config = [
            {"key": "hemoglobin", "label": "Huyết sắc tố", "type": "number"},
            {"key": "alt", "label": "ALT", "type": "number"},
        ]

    def _create_test_excel(self, rows: list[list]) -> bytes:
        """Helper to create a test Excel file."""
        wb = Workbook()
        ws = wb.active
        # Headers
        ws.append(["employee_code", "hemoglobin", "alt"])
        # Data rows
        for row in rows:
            ws.append(row)
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()

    def test_parse_valid_excel(self) -> None:
        """Parse a valid Excel file with employee_code and data."""
        file_content = self._create_test_excel(
            [
                ["NV001", 14.5, 25.0],
                ["NV002", 13.2, 30.0],
            ]
        )
        headers, rows = parse_department_import(file_content, self.fields_config)
        self.assertEqual(headers, ["employee_code", "hemoglobin", "alt"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["employee_code"], "NV001")
        self.assertEqual(rows[0]["hemoglobin"], 14.5)
        self.assertEqual(rows[1]["employee_code"], "NV002")

    def test_parse_missing_employee_code_raises_error(self) -> None:
        """Excel without employee_code column raises ValueError."""
        wb = Workbook()
        ws = wb.active
        ws.append(["name", "value"])  # No employee_code
        ws.append(["Test", 123])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        with self.assertRaises(ValueError) as ctx:
            parse_department_import(output.getvalue(), self.fields_config)
        self.assertIn("employee_code", str(ctx.exception))

    def test_parse_empty_excel_raises_error(self) -> None:
        """Empty Excel file raises ValueError."""
        wb = Workbook()
        ws = wb.active
        # No headers
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        with self.assertRaises(ValueError):
            parse_department_import(output.getvalue(), self.fields_config)


class ImportJobModelTest(TestCase):
    """Test ImportJob model."""

    def setUp(self) -> None:
        self.department = Department.objects.create(
            name="Xét nghiệm đặc biệt",
            code="xet_nghiem_dac_biet_test",
            category="para_clinical",
        )
        self.user = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            full_name="Admin User",
            role="admin",
        )
        self.job = ImportJob.objects.create(
            department=self.department,
            exam_date=date.today(),
            file=SimpleUploadedFile("test.xlsx", b"content"),
            created_by=self.user,
        )

    def test_import_job_creation(self) -> None:
        """ImportJob is created with default status=pending."""
        self.assertEqual(self.job.status, ImportJob.STATUS_PENDING)
        self.assertEqual(self.job.total_rows, 0)
        self.assertEqual(self.job.success_count, 0)
        self.assertIsNotNone(self.job.created_at)

    def test_import_job_str(self) -> None:
        """ImportJob __str__ includes department and date."""
        str_repr = str(self.job)
        self.assertIn("Xét nghiệm", str_repr)
        self.assertIn("pending", str_repr)


class DepartmentImportAPITest(TestCase):
    """Test per-department Excel import endpoint."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            full_name="Admin User",
            role="admin",
        )
        self.client.force_authenticate(user=self.admin)

        self.company = Company.objects.create(
            name="Test Company",
            code="TESTCO",
        )
        self.department = Department.objects.create(
            name="Xét nghiệm máu",
            code="xet_nghiem_mau",
            category="para_clinical",
        )
        self.template = _create_template(
            self.department,
            "Template XN",
            [{"key": "hemoglobin", "label": "Huyết sắc tố", "type": "number"}],
        )
        self.exam_package = ExamPackage.objects.create(
            name="Gói khám Test",
            exam_type="periodic",
        )
        ExamPackageDepartment.objects.create(
            exam_package=self.exam_package,
            department=self.department,
            template=self.template,
            order=0,
        )
        self.patient = Patient.objects.create(
            company=self.company,
            employee_code="NV001",
            full_name="Test Patient",
            dob=date(1990, 1, 1),
            gender="M",
        )

    def _get_post_data(self, **overrides) -> dict:
        """Get base POST data dict with defaults overridable."""
        data = {
            "company_id": str(self.company.id),
            "exam_package_id": str(self.exam_package.id),
            "exam_date": date.today().isoformat(),
        }
        data.update(overrides)
        return data

    def _create_test_excel(self) -> bytes:
        """Create a test Excel file with one patient."""
        wb = Workbook()
        ws = wb.active
        ws.append(["employee_code", "hemoglobin"])
        ws.append(["NV001", 14.5])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()

    def test_import_creates_import_job(self) -> None:
        """Import endpoint creates an ImportJob record."""
        file_content = self._create_test_excel()
        uploaded = SimpleUploadedFile("test.xlsx", file_content)
        url = f"/api/examinations/import/{self.department.id}/"
        response = self.client.post(
            url,
            {"file": uploaded, **self._get_post_data()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ImportJob.objects.count(), 1)
        job = ImportJob.objects.first()
        self.assertEqual(job.department, self.department)
        self.assertEqual(job.status, ImportJob.STATUS_COMPLETED)
        # Verify examination was created
        exam = Examination.objects.filter(
            patient=self.patient,
            exam_date=date.today(),
        ).first()
        self.assertIsNotNone(exam)
        self.assertEqual(exam.status, Examination.STATUS_COMPLETED)
        self.assertEqual(exam.doctor, self.admin)
        self.assertEqual(exam.exam_type, self.exam_package.exam_type)

    def test_import_updates_department_result(self) -> None:
        """Import updates DepartmentResult.data for the patient."""
        file_content = self._create_test_excel()
        uploaded = SimpleUploadedFile("test.xlsx", file_content)
        url = f"/api/examinations/import/{self.department.id}/"
        response = self.client.post(
            url,
            {"file": uploaded, **self._get_post_data()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Check examination was auto-created with confirmed status
        exam = Examination.objects.filter(
            patient=self.patient,
            exam_date=date.today(),
        ).first()
        self.assertIsNotNone(exam)
        self.assertEqual(exam.status, Examination.STATUS_COMPLETED)
        # Check DepartmentResult was created/updated
        dept_result = DepartmentResult.objects.filter(
            examination=exam,
            department=self.department,
        ).first()
        self.assertIsNotNone(dept_result)
        self.assertEqual(dept_result.data.get("hemoglobin"), 14.5)
        self.assertEqual(dept_result.completed_by, self.admin)

    def test_import_empty_field_uses_default_value(self) -> None:
        """Empty cells in import fall back to the field's default_value."""
        # Give the field a default value
        DepartmentField.objects.filter(
            template=self.template, key="hemoglobin"
        ).update(default_value="12")

        # Build an Excel where hemoglobin is left empty
        wb = Workbook()
        ws = wb.active
        ws.append(["employee_code", "hemoglobin"])
        ws.append(["NV001", None])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        uploaded = SimpleUploadedFile("test.xlsx", output.getvalue())

        url = f"/api/examinations/import/{self.department.id}/"
        response = self.client.post(
            url,
            {"file": uploaded, **self._get_post_data()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        exam = Examination.objects.filter(
            patient=self.patient, exam_date=date.today()
        ).first()
        dept_result = DepartmentResult.objects.get(
            examination=exam, department=self.department
        )
        # Empty cell → default_value "12" (as number)
        self.assertEqual(dept_result.data.get("hemoglobin"), 12.0)

    def test_import_empty_field_uses_random_in_range(self) -> None:
        """Empty numeric field without default → random value within range."""
        # Set a normal range but no default value
        DepartmentField.objects.filter(
            template=self.template, key="hemoglobin"
        ).update(normal_range_min=12, normal_range_max=16, default_value="")

        wb = Workbook()
        ws = wb.active
        ws.append(["employee_code", "hemoglobin"])
        ws.append(["NV001", None])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        uploaded = SimpleUploadedFile("test.xlsx", output.getvalue())

        url = f"/api/examinations/import/{self.department.id}/"
        response = self.client.post(
            url,
            {"file": uploaded, **self._get_post_data()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        exam = Examination.objects.filter(
            patient=self.patient, exam_date=date.today()
        ).first()
        dept_result = DepartmentResult.objects.get(
            examination=exam, department=self.department
        )
        val = dept_result.data.get("hemoglobin")
        self.assertIsNotNone(val)
        self.assertGreaterEqual(float(val), 12.0)
        self.assertLessEqual(float(val), 16.0)

    def test_import_null_string_uses_random_in_range(self) -> None:
        """Excel cells with 'null' / whitespace are treated as empty → random."""
        DepartmentField.objects.filter(
            template=self.template, key="hemoglobin"
        ).update(normal_range_min=12, normal_range_max=16, default_value="")

        wb = Workbook()
        ws = wb.active
        ws.append(["employee_code", "hemoglobin"])
        ws.append(["NV001", "null"])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        uploaded = SimpleUploadedFile("test.xlsx", output.getvalue())

        response = self.client.post(
            f"/api/examinations/import/{self.department.id}/",
            {"file": uploaded, **self._get_post_data()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        exam = Examination.objects.filter(
            patient=self.patient, exam_date=date.today()
        ).first()
        val = DepartmentResult.objects.get(
            examination=exam, department=self.department
        ).data.get("hemoglobin")
        self.assertIsNotNone(val)
        self.assertNotEqual(str(val).lower(), "null")
        self.assertGreaterEqual(float(val), 12.0)
        self.assertLessEqual(float(val), 16.0)

    def test_import_zero_is_not_replaced_by_random(self) -> None:
        DepartmentField.objects.filter(
            template=self.template, key="hemoglobin"
        ).update(normal_range_min=12, normal_range_max=16, default_value="")

        wb = Workbook()
        ws = wb.active
        ws.append(["employee_code", "hemoglobin"])
        ws.append(["NV001", 0])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        uploaded = SimpleUploadedFile("test.xlsx", output.getvalue())

        response = self.client.post(
            f"/api/examinations/import/{self.department.id}/",
            {"file": uploaded, **self._get_post_data()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        exam = Examination.objects.filter(
            patient=self.patient, exam_date=date.today()
        ).first()
        dept_result = DepartmentResult.objects.get(
            examination=exam, department=self.department
        )
        self.assertEqual(dept_result.data.get("hemoglobin"), 0.0)

    def test_import_missing_file_returns_error(self) -> None:
        """Import without file returns 400."""
        url = f"/api/examinations/import/{self.department.id}/"
        response = self.client.post(
            url,
            self._get_post_data(),
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data)

    def test_import_invalid_date_returns_error(self) -> None:
        """Import with invalid date returns 400."""
        file_content = self._create_test_excel()
        uploaded = SimpleUploadedFile("test.xlsx", file_content)
        url = f"/api/examinations/import/{self.department.id}/"
        response = self.client.post(
            url,
            {"file": uploaded, **self._get_post_data(exam_date="invalid-date")},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("exam_date", response.data)

    def test_import_nonexistent_patient_reports_error(self) -> None:
        """Import with unknown employee_code reports error in job."""
        wb = Workbook()
        ws = wb.active
        ws.append(["employee_code", "hemoglobin"])
        ws.append(["UNKNOWN", 14.5])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        uploaded = SimpleUploadedFile("test.xlsx", output.getvalue())
        url = f"/api/examinations/import/{self.department.id}/"
        response = self.client.post(
            url,
            {"file": uploaded, **self._get_post_data()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job = ImportJob.objects.first()
        self.assertEqual(job.skipped_count, 1)
        self.assertEqual(len(job.errors), 1)
        self.assertIn("UNKNOWN", job.errors[0]["message"])

    def test_import_missing_company_returns_error(self) -> None:
        """Import without company_id returns 400."""
        file_content = self._create_test_excel()
        uploaded = SimpleUploadedFile("test.xlsx", file_content)
        url = f"/api/examinations/import/{self.department.id}/"
        response = self.client.post(
            url,
            {
                "file": uploaded,
                "exam_package_id": str(self.exam_package.id),
                "exam_date": date.today().isoformat(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("company_id", response.data)

    def test_import_missing_exam_package_returns_error(self) -> None:
        """Import without exam_package_id returns 400."""
        file_content = self._create_test_excel()
        uploaded = SimpleUploadedFile("test.xlsx", file_content)
        url = f"/api/examinations/import/{self.department.id}/"
        response = self.client.post(
            url,
            {
                "file": uploaded,
                "company_id": str(self.company.id),
                "exam_date": date.today().isoformat(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("exam_package_id", response.data)


class ImportJobStatusAPITest(TestCase):
    """Test import job status endpoint."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            full_name="Admin User",
            role="admin",
        )
        self.client.force_authenticate(user=self.admin)

        self.department = Department.objects.create(
            name="Xét nghiệm import test",
            code="xet_nghiem_import_test",
            category="para_clinical",
        )
        self.job = ImportJob.objects.create(
            department=self.department,
            exam_date=date.today(),
            file=SimpleUploadedFile("test.xlsx", b"content"),
            created_by=self.admin,
            status=ImportJob.STATUS_COMPLETED,
            total_rows=10,
            success_count=8,
            updated_count=2,
        )

    def test_retrieve_import_job_status(self) -> None:
        """GET /api/import/{id}/ returns job status."""
        url = f"/api/import/{self.job.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.job.id))
        self.assertEqual(response.data["status"], ImportJob.STATUS_COMPLETED)
        self.assertEqual(response.data["total_rows"], 10)
        self.assertEqual(response.data["success_count"], 8)

    def test_list_import_jobs(self) -> None:
        """GET /api/import/ lists all import jobs for admin."""
        url = "/api/import/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)


class TemplateExportAPITest(TestCase):
    """Test template export endpoint."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            full_name="Admin User",
            role="admin",
        )
        self.client.force_authenticate(user=self.admin)

        self.department = Department.objects.create(
            name="Xét nghiệm máu",
            code="xet_nghiem_mau",
            category="para_clinical",
        )
        self.template = _create_template(
            self.department,
            "Template XN",
            [
                {
                    "key": "hemoglobin",
                    "label": "Huyết sắc tố",
                    "type": "number",
                    "unit": "g/dL",
                },
            ],
        )

    def test_export_template_returns_xlsx(self) -> None:
        """GET /api/templates/{id}/export-template/ returns .xlsx file."""
        url = f"/api/templates/{self.template.id}/export-template/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("application/vnd.openxmlformats", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".xlsx", response["Content-Disposition"])

    def test_export_template_contains_employee_code(self) -> None:
        """Exported template has employee_code as first column."""
        url = f"/api/templates/{self.template.id}/export-template/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Parse the returned file
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(response.content))
        ws = wb.active
        self.assertEqual(ws.cell(row=1, column=1).value, "employee_code")
        wb.close()
