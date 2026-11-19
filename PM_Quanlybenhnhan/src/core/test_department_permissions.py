"""
Tests for Sprint 2a — Department-level Roles & Permissions.

Covers the department-based RBAC update:
- ROLE_DEPARTMENT_ACCESS helpers
- DepartmentResultPermission (category + code based)
- Editable-departments API endpoint
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.permissions import (
    DEPARTMENT_CATEGORY_CLINICAL,
    DEPARTMENT_CATEGORY_PARACLINICAL,
    ROLE_ADMIN,
    ROLE_DOCTOR,
    ROLE_LABTECH,
    ROLE_NURSE,
    WILDCARD,
    DepartmentResultPermission,
    can_edit_department,
    can_edit_department_category,
    can_edit_department_code,
    get_editable_department_codes,
)

User = get_user_model()


def _make_user(role: str, **kwargs) -> User:
    email = kwargs.pop("email", f"{role}@dept.test")
    return User.objects.create_user(
        email=email,
        password="TestPass123!",
        full_name=f"Test {role.title()}",
        role=role,
        **kwargs,
    )


def _dept(code: str | None = None, category: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(code=code, category=category)


def _make_request(user, method="GET") -> MagicMock:
    request = MagicMock()
    request.method = method
    request.user = user
    return request


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestDepartmentAccessHelpers(TestCase):
    def test_category_access_nurse(self) -> None:
        self.assertTrue(
            can_edit_department_category(ROLE_NURSE, DEPARTMENT_CATEGORY_CLINICAL)
        )
        self.assertFalse(
            can_edit_department_category(
                ROLE_NURSE, DEPARTMENT_CATEGORY_PARACLINICAL
            )
        )

    def test_category_access_labtech(self) -> None:
        self.assertTrue(
            can_edit_department_category(
                ROLE_LABTECH, DEPARTMENT_CATEGORY_PARACLINICAL
            )
        )
        self.assertFalse(
            can_edit_department_category(
                ROLE_LABTECH, DEPARTMENT_CATEGORY_CLINICAL
            )
        )

    def test_category_access_doctor_and_admin_wildcard(self) -> None:
        for role in (ROLE_DOCTOR, ROLE_ADMIN):
            self.assertTrue(
                can_edit_department_category(role, DEPARTMENT_CATEGORY_CLINICAL)
            )
            self.assertTrue(
                can_edit_department_category(
                    role, DEPARTMENT_CATEGORY_PARACLINICAL
                )
            )

    def test_code_access_nurse(self) -> None:
        self.assertTrue(can_edit_department_code(ROLE_NURSE, "kham_lam_sang"))
        self.assertTrue(can_edit_department_code(ROLE_NURSE, "mat"))
        self.assertFalse(can_edit_department_code(ROLE_NURSE, "xet_nghiem"))

    def test_code_access_labtech(self) -> None:
        self.assertTrue(can_edit_department_code(ROLE_LABTECH, "xet_nghiem"))
        self.assertTrue(can_edit_department_code(ROLE_LABTECH, "x_quang"))
        self.assertTrue(can_edit_department_code(ROLE_LABTECH, "sieu_am"))
        self.assertFalse(can_edit_department_code(ROLE_LABTECH, "kham_lam_sang"))

    def test_code_access_doctor_wildcard(self) -> None:
        self.assertTrue(can_edit_department_code(ROLE_DOCTOR, "anything"))

    def test_can_edit_department_prefers_category(self) -> None:
        # Nurse + clinical category → allowed even if code unknown
        dept = _dept(code="unknown_code", category=DEPARTMENT_CATEGORY_CLINICAL)
        self.assertTrue(can_edit_department(ROLE_NURSE, dept))
        # Nurse + para-clinical category → denied
        dept2 = _dept(
            code="kham_lam_sang", category=DEPARTMENT_CATEGORY_PARACLINICAL
        )
        self.assertFalse(can_edit_department(ROLE_NURSE, dept2))

    def test_can_edit_department_falls_back_to_code(self) -> None:
        dept = _dept(code="xet_nghiem", category=None)
        self.assertTrue(can_edit_department(ROLE_LABTECH, dept))
        self.assertFalse(can_edit_department(ROLE_NURSE, dept))

    def test_get_editable_department_codes(self) -> None:
        self.assertEqual(get_editable_department_codes(ROLE_DOCTOR), [WILDCARD])
        self.assertEqual(get_editable_department_codes(ROLE_ADMIN), [WILDCARD])
        self.assertIn("kham_lam_sang", get_editable_department_codes(ROLE_NURSE))
        self.assertIn("xet_nghiem", get_editable_department_codes(ROLE_LABTECH))
        self.assertEqual(get_editable_department_codes("company_admin"), [])


# ---------------------------------------------------------------------------
# DepartmentResultPermission tests
# ---------------------------------------------------------------------------


class TestDepartmentResultPermission(TestCase):
    def setUp(self) -> None:
        self.admin = _make_user(ROLE_ADMIN, email="admin@dr.test")
        self.doctor = _make_user(ROLE_DOCTOR, email="doctor@dr.test")
        self.nurse = _make_user(ROLE_NURSE, email="nurse@dr.test")
        self.labtech = _make_user(ROLE_LABTECH, email="labtech@dr.test")
        self.perm = DepartmentResultPermission()

    def _result(self, category, exam_status="draft") -> SimpleNamespace:
        return SimpleNamespace(
            department=_dept(category=category),
            examination=SimpleNamespace(status=exam_status),
        )

    # --- has_permission with view.get_department() ---

    def test_view_level_department_check_nurse_clinical(self) -> None:
        view = MagicMock()
        view.get_department.return_value = _dept(
            category=DEPARTMENT_CATEGORY_CLINICAL
        )
        req = _make_request(self.nurse, method="PUT")
        self.assertTrue(self.perm.has_permission(req, view))

    def test_view_level_department_check_nurse_paraclinical_denied(self) -> None:
        view = MagicMock()
        view.get_department.return_value = _dept(
            category=DEPARTMENT_CATEGORY_PARACLINICAL
        )
        req = _make_request(self.nurse, method="PUT")
        self.assertFalse(self.perm.has_permission(req, view))

    def test_read_allowed_for_clinical_staff(self) -> None:
        view = MagicMock()
        view.get_department.return_value = None
        for user in (self.admin, self.doctor, self.nurse, self.labtech):
            req = _make_request(user, method="GET")
            self.assertTrue(self.perm.has_permission(req, view))

    # --- has_object_permission ---

    def test_nurse_can_edit_clinical_result(self) -> None:
        obj = self._result(DEPARTMENT_CATEGORY_CLINICAL)
        req = _make_request(self.nurse, method="PUT")
        self.assertTrue(self.perm.has_object_permission(req, MagicMock(), obj))

    def test_nurse_cannot_edit_paraclinical_result(self) -> None:
        obj = self._result(DEPARTMENT_CATEGORY_PARACLINICAL)
        req = _make_request(self.nurse, method="PUT")
        self.assertFalse(self.perm.has_object_permission(req, MagicMock(), obj))

    def test_labtech_can_edit_paraclinical_result(self) -> None:
        obj = self._result(DEPARTMENT_CATEGORY_PARACLINICAL)
        req = _make_request(self.labtech, method="PUT")
        self.assertTrue(self.perm.has_object_permission(req, MagicMock(), obj))

    def test_labtech_cannot_edit_clinical_result(self) -> None:
        obj = self._result(DEPARTMENT_CATEGORY_CLINICAL)
        req = _make_request(self.labtech, method="PUT")
        self.assertFalse(self.perm.has_object_permission(req, MagicMock(), obj))

    def test_doctor_can_edit_any_result(self) -> None:
        for category in (
            DEPARTMENT_CATEGORY_CLINICAL,
            DEPARTMENT_CATEGORY_PARACLINICAL,
        ):
            obj = self._result(category)
            req = _make_request(self.doctor, method="PUT")
            self.assertTrue(self.perm.has_object_permission(req, MagicMock(), obj))

    def test_confirmed_exam_immutable_for_non_admin(self) -> None:
        obj = self._result(DEPARTMENT_CATEGORY_CLINICAL, exam_status="confirmed")
        req = _make_request(self.nurse, method="PUT")
        self.assertFalse(self.perm.has_object_permission(req, MagicMock(), obj))

    def test_admin_can_edit_confirmed_exam(self) -> None:
        obj = self._result(DEPARTMENT_CATEGORY_PARACLINICAL, exam_status="confirmed")
        req = _make_request(self.admin, method="PUT")
        self.assertTrue(self.perm.has_object_permission(req, MagicMock(), obj))


# ---------------------------------------------------------------------------
# Editable-departments API endpoint tests
# ---------------------------------------------------------------------------


class TestEditableDepartmentsEndpoint(APITestCase):
    def setUp(self) -> None:
        self.nurse = _make_user(ROLE_NURSE, email="nurse@api.test")
        self.labtech = _make_user(ROLE_LABTECH, email="labtech@api.test")
        self.doctor = _make_user(ROLE_DOCTOR, email="doctor@api.test")
        self.url = reverse("accounts:editable_departments")

    def test_requires_authentication(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nurse_editable_departments(self) -> None:
        self.client.force_authenticate(user=self.nurse)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["role"], ROLE_NURSE)
        self.assertFalse(body["all_departments"])
        self.assertIn("kham_lam_sang", body["editable_department_codes"])
        self.assertIn(
            DEPARTMENT_CATEGORY_CLINICAL, body["editable_categories"]
        )

    def test_labtech_editable_departments(self) -> None:
        self.client.force_authenticate(user=self.labtech)
        response = self.client.get(self.url)
        body = response.json()
        self.assertIn("xet_nghiem", body["editable_department_codes"])
        self.assertIn(
            DEPARTMENT_CATEGORY_PARACLINICAL, body["editable_categories"]
        )

    def test_doctor_all_departments(self) -> None:
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get(self.url)
        body = response.json()
        self.assertTrue(body["all_departments"])
        self.assertEqual(body["editable_department_codes"], [WILDCARD])
        self.assertEqual(body["editable_categories"], [WILDCARD])
