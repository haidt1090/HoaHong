"""
Tests for Phase 1 — Sprint 3: Patient & Company Management.

Covers:
- Patient & Company model behaviour (soft delete, conditional unique constraint)
- Patient CRUD API + role scoping (including cá nhân patients)
- Company CRUD API + role scoping
- Search, filtering, pagination
- Examination history timeline (empty until Sprint 5)
- CompanyExamPackage CRUD
- Group permission seeding
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Company, CompanyExamPackage, StaffAssignment
from examinations.models import ExamPackage
from patients.models import Patient

User = get_user_model()


def _make_user(role: str, **kwargs) -> User:
    email = kwargs.pop("email", f"{role}@patients.test")
    return User.objects.create_user(
        email=email,
        password="TestPass123!",
        full_name=f"Test {role.title()}",
        role=role,
        **kwargs,
    )


def _make_patient(company: Company | None = None, **kwargs) -> Patient:
    defaults: dict = {
        "full_name": "Nguyễn Văn A",
        "dob": date(1990, 1, 1),
        "gender": "M",
    }
    if company is not None:
        defaults["company"] = company
        defaults.setdefault("employee_code", "EMP001")
    defaults.update(kwargs)
    return Patient.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class PatientModelTests(APITestCase):
    def setUp(self) -> None:
        self.company = Company.objects.create(name="Công ty A", code="CTA")

    def test_unique_together_company_employee_code(self) -> None:
        _make_patient(self.company, employee_code="E1")
        with self.assertRaises(IntegrityError):
            _make_patient(self.company, employee_code="E1", full_name="Khác")

    def test_same_employee_code_different_company_allowed(self) -> None:
        company_b = Company.objects.create(name="Công ty B", code="CTB")
        _make_patient(self.company, employee_code="E1")
        _make_patient(company_b, employee_code="E1", full_name="Người khác")
        self.assertEqual(Patient.objects.count(), 2)

    def test_ca_nhan_patient_no_company_works(self) -> None:
        """Cá nhân patient: company=None, employee_code optional."""
        patient = _make_patient(None, employee_code="", full_name="Cá Nhân A")
        self.assertIsNone(patient.company)
        self.assertEqual(patient.employee_code, "")
        self.assertEqual(patient.full_name, "Cá Nhân A")

    def test_ca_nhan_duplicate_employee_code_no_constraint(self) -> None:
        """NULL company has no unique constraint — duplicates allowed."""
        _make_patient(None, employee_code="CA", full_name="A")
        _make_patient(None, employee_code="CA", full_name="B")
        self.assertEqual(Patient.objects.count(), 2)

    def test_str_with_company(self) -> None:
        patient = _make_patient(self.company, employee_code="E9", full_name="Trần B")
        self.assertIn("Trần B", str(patient))
        self.assertIn("E9", str(patient))

    def test_str_without_company(self) -> None:
        patient = _make_patient(None, full_name="Cá Nhân Z")
        self.assertNotIn("(", str(patient))


# ---------------------------------------------------------------------------
# Patient CRUD API tests
# ---------------------------------------------------------------------------


class PatientCrudApiTests(APITestCase):
    def setUp(self) -> None:
        cache.clear()
        self.company = Company.objects.create(name="Công ty A", code="CTA")
        self.admin = _make_user("admin", email="admin@patients.test")
        self.doctor = _make_user("doctor", email="doctor@patients.test")

    def _patient_payload(self, **overrides) -> dict:
        payload: dict = {
            "company": str(self.company.id),
            "employee_code": "EMP100",
            "full_name": "Lê Văn C",
            "dob": "1985-05-20",
            "gender": "M",
            "phone": "0909123456",
            "department": "Sản xuất",
        }
        payload.update(overrides)
        return payload

    def test_admin_can_create_patient(self) -> None:
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            reverse("patients:patient-list"),
            self._patient_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Patient.objects.count(), 1)

    def test_admin_can_create_ca_nhan_patient(self) -> None:
        """Create a cá nhân patient without company."""
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            reverse("patients:patient-list"),
            {
                "full_name": "Người Dân",
                "dob": "1992-03-15",
                "gender": "F",
                "phone": "0900111222",
                "cccd": "012345678912",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        patient = Patient.objects.get(id=response.data["id"])
        self.assertIsNone(patient.company)
        self.assertEqual(patient.full_name, "Người Dân")

    def test_create_requires_employee_code_when_company_set(self) -> None:
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            reverse("patients:patient-list"),
            {
                "company": str(self.company.id),
                "full_name": "Thiếu Mã",
                "dob": "2000-01-01",
                "gender": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("employee_code", response.data)

    def test_doctor_cannot_create_patient(self) -> None:
        self.client.force_authenticate(self.doctor)
        response = self.client.post(
            reverse("patients:patient-list"),
            self._patient_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_employee_code_rejected(self) -> None:
        _make_patient(self.company, employee_code="EMP100")
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            reverse("patients:patient-list"),
            self._patient_payload(employee_code="EMP100"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_update_patient(self) -> None:
        patient = _make_patient(self.company, employee_code="EMP100")
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            reverse("patients:patient-detail", args=[patient.id]),
            {"full_name": "Tên Mới"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        patient.refresh_from_db()
        self.assertEqual(patient.full_name, "Tên Mới")

    def test_delete_performs_soft_delete(self) -> None:
        patient = _make_patient(self.company, employee_code="EMP100")
        self.client.force_authenticate(self.admin)
        response = self.client.delete(
            reverse("patients:patient-detail", args=[patient.id])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        patient.refresh_from_db()
        self.assertFalse(patient.is_active)
        response = self.client.get(
            reverse("patients:patient-detail", args=[patient.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_doctor_cannot_delete_patient(self) -> None:
        patient = _make_patient(self.company, employee_code="EMP100")
        self.client.force_authenticate(self.doctor)
        response = self.client.delete(
            reverse("patients:patient-detail", args=[patient.id])
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_soft_deleted_hidden_from_doctor(self) -> None:
        patient = _make_patient(self.company, employee_code="EMP100", is_active=False)
        self.client.force_authenticate(self.doctor)
        response = self.client.get(
            reverse("patients:patient-detail", args=[patient.id])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_reactivate_patient(self) -> None:
        patient = _make_patient(self.company, employee_code="EMP100", is_active=False)
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            reverse("patients:patient-reactivate", args=[patient.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        patient.refresh_from_db()
        self.assertTrue(patient.is_active)

    def test_detail_returns_examination_timeline_field(self) -> None:
        patient = _make_patient(self.company, employee_code="EMP100")
        self.client.force_authenticate(self.admin)
        response = self.client.get(
            reverse("patients:patient-detail", args=[patient.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("examinations", response.data)
        self.assertEqual(response.data["examinations"], [])

    def test_unauthenticated_denied(self) -> None:
        response = self.client.get(reverse("patients:patient-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Search / filter / pagination tests
# ---------------------------------------------------------------------------


class PatientSearchFilterTests(APITestCase):
    def setUp(self) -> None:
        cache.clear()
        self.company_a = Company.objects.create(name="Công ty A", code="CTA")
        self.company_b = Company.objects.create(name="Công ty B", code="CTB")
        self.admin = _make_user("admin", email="admin@search.test")
        self.client.force_authenticate(self.admin)

        _make_patient(
            self.company_a,
            employee_code="EMP001",
            full_name="Nguyễn Văn An",
            cccd="012345678901",
            phone="0900000001",
            department="Sản xuất",
            gender="M",
        )
        _make_patient(
            self.company_a,
            employee_code="EMP002",
            full_name="Trần Thị Bình",
            cccd="012345678902",
            phone="0900000002",
            department="Kế toán",
            gender="F",
        )
        _make_patient(
            self.company_b,
            employee_code="XYZ003",
            full_name="Lê Văn Cường",
            cccd="099999999999",
            phone="0900000003",
            department="Sản xuất",
            gender="M",
        )
        _make_patient(
            None, full_name="Người Cá Nhân", cccd="111111111111", phone="0900000004"
        )

    def test_search_by_name(self) -> None:
        response = self.client.get(reverse("patients:patient-list"), {"search": "Bình"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["full_name"], "Trần Thị Bình")

    def test_search_by_employee_code(self) -> None:
        response = self.client.get(
            reverse("patients:patient-list"), {"search": "XYZ003"}
        )
        self.assertEqual(response.data["count"], 1)

    def test_search_by_cccd(self) -> None:
        response = self.client.get(
            reverse("patients:patient-list"), {"search": "099999999999"}
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["full_name"], "Lê Văn Cường")

    def test_search_by_company_code(self) -> None:
        # company_b has code "CTB"; only its 1 patient should match.
        response = self.client.get(reverse("patients:patient-list"), {"search": "CTB"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["full_name"], "Lê Văn Cường")

    def test_search_by_phone(self) -> None:
        response = self.client.get(
            reverse("patients:patient-list"), {"search": "0900000002"}
        )
        self.assertEqual(response.data["count"], 1)

    def test_filter_by_company(self) -> None:
        response = self.client.get(
            reverse("patients:patient-list"), {"company": str(self.company_a.id)}
        )
        self.assertEqual(response.data["count"], 2)

    def test_filter_by_company_code(self) -> None:
        response = self.client.get(
            reverse("patients:patient-list"), {"company_code": "CTB"}
        )
        self.assertEqual(response.data["count"], 1)

    def test_filter_by_department(self) -> None:
        response = self.client.get(
            reverse("patients:patient-list"), {"department": "Sản xuất"}
        )
        self.assertEqual(response.data["count"], 2)

    def test_filter_by_gender(self) -> None:
        response = self.client.get(reverse("patients:patient-list"), {"gender": "F"})
        self.assertEqual(response.data["count"], 1)

    def test_filter_has_company_true(self) -> None:
        response = self.client.get(
            reverse("patients:patient-list"), {"has_company": "true"}
        )
        self.assertEqual(response.data["count"], 3)

    def test_filter_has_company_false(self) -> None:
        response = self.client.get(
            reverse("patients:patient-list"), {"has_company": "false"}
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["full_name"], "Người Cá Nhân")

    def test_pagination_metadata_present(self) -> None:
        response = self.client.get(reverse("patients:patient-list"))
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 4)

    def test_page_size_query_param(self) -> None:
        response = self.client.get(reverse("patients:patient-list"), {"page_size": 2})
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])


# ---------------------------------------------------------------------------
# Role scoping tests
# ---------------------------------------------------------------------------


class PatientRoleScopingTests(APITestCase):
    def setUp(self) -> None:
        cache.clear()
        self.company_a = Company.objects.create(name="Công ty A", code="CTA")
        self.company_b = Company.objects.create(name="Công ty B", code="CTB")

        _make_patient(self.company_a, employee_code="A1", full_name="A One")
        _make_patient(self.company_b, employee_code="B1", full_name="B One")
        _make_patient(None, full_name="Cá Nhân X")

    def test_doctor_sees_all_active_plus_ca_nhan(self) -> None:
        doctor = _make_user("doctor", email="doctor@scope.test")
        self.client.force_authenticate(doctor)
        response = self.client.get(reverse("patients:patient-list"))
        self.assertEqual(response.data["count"], 3)

    def test_company_admin_sees_only_own_company(self) -> None:
        cadmin = _make_user(
            "company_admin", email="cadmin@scope.test", company=self.company_a
        )
        self.client.force_authenticate(cadmin)
        response = self.client.get(reverse("patients:patient-list"))
        # Own company only (1); cá nhân patients are NOT visible to CompanyAdmin.
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["full_name"], "A One")

    def test_labtech_sees_assigned_plus_ca_nhan(self) -> None:
        labtech = _make_user("labtech", email="labtech@scope.test")
        StaffAssignment.objects.create(user=labtech, company=self.company_b)
        self.client.force_authenticate(labtech)
        response = self.client.get(reverse("patients:patient-list"))
        # Assigned company B (1) + cá nhân (1) = 2
        self.assertEqual(response.data["count"], 2)

    def test_labtech_without_assignment_sees_only_ca_nhan(self) -> None:
        labtech = _make_user("labtech", email="labtech2@scope.test")
        self.client.force_authenticate(labtech)
        response = self.client.get(reverse("patients:patient-list"))
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["full_name"], "Cá Nhân X")

    def test_admin_sees_inactive_patients(self) -> None:
        _make_patient(
            self.company_a,
            employee_code="A2",
            full_name="Inactive",
            is_active=False,
        )
        admin = _make_user("admin", email="admin@scope.test")
        self.client.force_authenticate(admin)
        response = self.client.get(reverse("patients:patient-list"))
        # 2 active + 1 inactive + 1 cá nhân = 4
        self.assertEqual(response.data["count"], 4)


# ---------------------------------------------------------------------------
# Company CRUD API tests
# ---------------------------------------------------------------------------


class CompanyCrudApiTests(APITestCase):
    def setUp(self) -> None:
        cache.clear()
        self.admin = _make_user("admin", email="admin@company.test")
        self.doctor = _make_user("doctor", email="doctor@company.test")
        self.nurse = _make_user("nurse", email="nurse@company.test")

    def _payload(self, **overrides) -> dict:
        payload = {
            "name": "Công ty Mới",
            "code": "NEW01",
            "tax_code": "0101010101",
            "contact_person": "Người liên hệ",
        }
        payload.update(overrides)
        return payload

    def test_admin_can_create_company(self) -> None:
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            reverse("patients:company-list"), self._payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Company.objects.count(), 1)

    def test_doctor_can_read_but_not_create_company(self) -> None:
        Company.objects.create(name="Existing", code="EX01")
        self.client.force_authenticate(self.doctor)
        list_resp = self.client.get(reverse("patients:company-list"))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        create_resp = self.client.post(
            reverse("patients:company-list"), self._payload(), format="json"
        )
        self.assertEqual(create_resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_nurse_cannot_read_companies(self) -> None:
        self.client.force_authenticate(self.nurse)
        response = self.client.get(reverse("patients:company-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_company_soft_delete(self) -> None:
        company = Company.objects.create(name="ToDelete", code="DEL01")
        self.client.force_authenticate(self.admin)
        response = self.client.delete(
            reverse("patients:company-detail", args=[company.id])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        company.refresh_from_db()
        self.assertFalse(company.is_active)

    def test_company_patient_count_annotation(self) -> None:
        company = Company.objects.create(name="Counted", code="CNT01")
        _make_patient(company, employee_code="P1")
        _make_patient(company, employee_code="P2", is_active=False)
        self.client.force_authenticate(self.admin)
        response = self.client.get(
            reverse("patients:company-detail", args=[company.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["patient_count"], 1)


# ---------------------------------------------------------------------------
# CompanyExamPackage CRUD API tests
# ---------------------------------------------------------------------------


class CompanyExamPackageApiTests(APITestCase):
    def setUp(self) -> None:
        cache.clear()
        self.company = Company.objects.create(name="Công ty A", code="CTA")
        self.admin = _make_user("admin", email="admin@pkg.test")
        self.doctor = _make_user("doctor", email="doctor@pkg.test")
        self.exam_package = ExamPackage.objects.create(
            name="Gói định kỳ", exam_type="periodic"
        )
        self.exam_package_2 = ExamPackage.objects.create(
            name="Gói nghề nghiệp", exam_type="occupational"
        )

    def _url(self, pk: str | None = None) -> str:
        base = reverse(
            "patients:company-package-list",
            kwargs={"company_pk": self.company.id},
        )
        if pk:
            return reverse(
                "patients:company-package-detail",
                kwargs={"company_pk": self.company.id, "pk": pk},
            )
        return base

    def _payload(self, **overrides) -> dict:
        payload = {
            "exam_package": str(self.exam_package.id),
            "pricing_mode": "per_field",
            "total_employees": 50,
            "is_active": True,
        }
        payload.update(overrides)
        return payload

    def test_admin_can_create_package(self) -> None:
        self.client.force_authenticate(self.admin)
        response = self.client.post(self._url(), self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(CompanyExamPackage.objects.count(), 1)

    def test_admin_can_list_packages(self) -> None:
        CompanyExamPackage.objects.create(
            company=self.company,
            exam_package=self.exam_package,
            pricing_mode="per_field",
            assigned_by=self.admin,
        )
        self.client.force_authenticate(self.admin)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_doctor_cannot_create_package(self) -> None:
        self.client.force_authenticate(self.doctor)
        response = self.client.post(self._url(), self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_packages_scoped_to_company(self) -> None:
        CompanyExamPackage.objects.create(
            company=self.company,
            exam_package=self.exam_package,
            pricing_mode="per_field",
            assigned_by=self.admin,
        )
        company_b = Company.objects.create(name="Công ty B", code="CTB")
        CompanyExamPackage.objects.create(
            company=company_b,
            exam_package=self.exam_package_2,
            pricing_mode="package_total",
            assigned_by=self.admin,
        )
        self.client.force_authenticate(self.admin)
        response = self.client.get(self._url())
        self.assertEqual(response.data["count"], 1)

    def test_duplicate_package_per_company_rejected(self) -> None:
        CompanyExamPackage.objects.create(
            company=self.company,
            exam_package=self.exam_package,
            pricing_mode="per_field",
            assigned_by=self.admin,
        )
        self.client.force_authenticate(self.admin)
        response = self.client.post(self._url(), self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_price_preview_per_field_mode(self) -> None:
        from examinations.models import Department, DepartmentField, DepartmentTemplate, ExamPackageDepartment

        dept = Department.objects.create(name="Xét nghiệm", code="XN", category="para_clinical")
        tpl = DepartmentTemplate.objects.create(department=dept, name="Mẫu XN")
        DepartmentField.objects.create(template=tpl, key="hb", label="Huyết sắc tố", unit="g/dL", default_price=50000)
        DepartmentField.objects.create(template=tpl, key="alt", label="ALT", unit="U/L", default_price=40000)
        ExamPackageDepartment.objects.create(
            exam_package=self.exam_package, department=dept, template=tpl, order=1
        )

        cep = CompanyExamPackage.objects.create(
            company=self.company,
            exam_package=self.exam_package,
            pricing_mode="per_field",
            total_employees=50,
            assigned_by=self.admin,
        )

        self.client.force_authenticate(self.admin)
        url = self._url(cep.id) + "price-preview/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["mode"], "per_field")
        self.assertEqual(response.data["total_employees"], 50)
        self.assertEqual(response.data["cost_per_employee"], 90000)
        self.assertEqual(response.data["grand_total"], 4500000)

    def test_price_preview_package_total_mode(self) -> None:
        self.exam_package.default_package_price = 500000
        self.exam_package.save()

        cep = CompanyExamPackage.objects.create(
            company=self.company,
            exam_package=self.exam_package,
            pricing_mode="package_total",
            total_employees=50,
            assigned_by=self.admin,
        )

        self.client.force_authenticate(self.admin)
        url = self._url(cep.id) + "price-preview/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["mode"], "package_total")
        self.assertEqual(response.data["cost_per_employee"], 500000)
        self.assertEqual(response.data["grand_total"], 25000000)

    def test_price_preview_with_employees_override(self) -> None:
        cep = CompanyExamPackage.objects.create(
            company=self.company,
            exam_package=self.exam_package,
            pricing_mode="package_total",
            total_employees=50,
            assigned_by=self.admin,
        )

        self.client.force_authenticate(self.admin)
        url = self._url(cep.id) + "price-preview/?total_employees=100"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_employees"], 100)


# ---------------------------------------------------------------------------
# Group permission seeding
# ---------------------------------------------------------------------------


class PatientGroupPermissionsTests(APITestCase):
    def test_admin_group_has_patient_crud(self) -> None:
        group = Group.objects.get(name="admin")
        perms = list(group.permissions.values_list("codename", flat=True))
        for action in [
            "add_patient",
            "change_patient",
            "delete_patient",
            "view_patient",
        ]:
            self.assertIn(action, perms)

    def test_doctor_group_has_view_patient_only(self) -> None:
        group = Group.objects.get(name="doctor")
        perms = list(group.permissions.values_list("codename", flat=True))
        self.assertIn("view_patient", perms)
        self.assertNotIn("add_patient", perms)
        self.assertNotIn("delete_patient", perms)

    def test_admin_group_has_companyexampackage_crud(self) -> None:
        group = Group.objects.get(name="admin")
        perms = list(group.permissions.values_list("codename", flat=True))
        for action in [
            "add_companyexampackage",
            "change_companyexampackage",
            "delete_companyexampackage",
            "view_companyexampackage",
        ]:
            self.assertIn(action, perms)
