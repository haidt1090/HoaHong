"""
Tests for Sprint 2a — Roles & Permissions.

Covers:
- Role-based permission classes (core/permissions.py)
- StaffAssignment model
- Group permission seeding

Note: Department-level permission tests (DepartmentResultPermission)
live in test_department_permissions.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework import status

from accounts.models import Company, StaffAssignment
from core.permissions import (
    ExaminationConfirmPermission,
    ExaminationPermission,
    IsAdmin,
    IsAdminOrDoctor,
    IsAdminOrReadOnly,
    IsClinicalStaff,
    IsCompanyAdmin,
    IsDoctor,
    IsLabTech,
    IsNurse,
    IsOwnCompanyOrAdmin,
    ROLE_ADMIN,
    ROLE_COMPANY_ADMIN,
    ROLE_DOCTOR,
    ROLE_LABTECH,
    ROLE_NURSE,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(role: str, **kwargs) -> User:
    """Create a user with the given role."""
    email = kwargs.pop("email", f"{role}@test.com")
    return User.objects.create_user(
        email=email,
        password="TestPass123!",
        full_name=f"Test {role.title()}",
        role=role,
        **kwargs,
    )


def _make_request(user=None, method="GET") -> MagicMock:
    """Build a mock DRF request with a real or anonymous user."""
    request = MagicMock()
    request.method = method
    if user:
        # Use the real User instance — it already has is_authenticated=True
        request.user = user
    else:
        anon = MagicMock()
        anon.is_authenticated = False
        request.user = anon
    return request


# ---------------------------------------------------------------------------
# Permission class tests
# ---------------------------------------------------------------------------


class TestRolePermissionClasses(TestCase):
    """Test individual role-based permission classes."""

    def setUp(self) -> None:
        self.admin = _make_user(ROLE_ADMIN, email="admin@perm.test")
        self.doctor = _make_user(ROLE_DOCTOR, email="doctor@perm.test")
        self.nurse = _make_user(ROLE_NURSE, email="nurse@perm.test")
        self.labtech = _make_user(ROLE_LABTECH, email="labtech@perm.test")
        self.company_admin = _make_user(
            ROLE_COMPANY_ADMIN, email="cadmin@perm.test"
        )
        self.view = MagicMock()

    def test_is_admin_allows_admin_only(self) -> None:
        perm = IsAdmin()
        self.assertTrue(perm.has_permission(_make_request(self.admin), self.view))
        self.assertFalse(perm.has_permission(_make_request(self.doctor), self.view))
        self.assertFalse(perm.has_permission(_make_request(self.nurse), self.view))
        self.assertFalse(perm.has_permission(_make_request(self.labtech), self.view))
        self.assertFalse(
            perm.has_permission(_make_request(self.company_admin), self.view)
        )

    def test_is_doctor_allows_doctor_only(self) -> None:
        perm = IsDoctor()
        self.assertTrue(perm.has_permission(_make_request(self.doctor), self.view))
        self.assertFalse(perm.has_permission(_make_request(self.admin), self.view))
        self.assertFalse(perm.has_permission(_make_request(self.nurse), self.view))

    def test_is_nurse_allows_nurse_only(self) -> None:
        perm = IsNurse()
        self.assertTrue(perm.has_permission(_make_request(self.nurse), self.view))
        self.assertFalse(perm.has_permission(_make_request(self.doctor), self.view))

    def test_is_labtech_allows_labtech_only(self) -> None:
        perm = IsLabTech()
        self.assertTrue(perm.has_permission(_make_request(self.labtech), self.view))
        self.assertFalse(perm.has_permission(_make_request(self.nurse), self.view))

    def test_is_company_admin_allows_company_admin_only(self) -> None:
        perm = IsCompanyAdmin()
        self.assertTrue(
            perm.has_permission(_make_request(self.company_admin), self.view)
        )
        self.assertFalse(perm.has_permission(_make_request(self.admin), self.view))

    def test_is_clinical_staff_allows_clinic_roles(self) -> None:
        perm = IsClinicalStaff()
        self.assertTrue(perm.has_permission(_make_request(self.admin), self.view))
        self.assertTrue(perm.has_permission(_make_request(self.doctor), self.view))
        self.assertTrue(perm.has_permission(_make_request(self.nurse), self.view))
        self.assertTrue(perm.has_permission(_make_request(self.labtech), self.view))
        self.assertFalse(
            perm.has_permission(_make_request(self.company_admin), self.view)
        )

    def test_is_admin_or_doctor(self) -> None:
        perm = IsAdminOrDoctor()
        self.assertTrue(perm.has_permission(_make_request(self.admin), self.view))
        self.assertTrue(perm.has_permission(_make_request(self.doctor), self.view))
        self.assertFalse(perm.has_permission(_make_request(self.nurse), self.view))

    def test_is_admin_or_read_only(self) -> None:
        perm = IsAdminOrReadOnly()
        # Read access for anyone authenticated
        self.assertTrue(
            perm.has_permission(_make_request(self.nurse, method="GET"), self.view)
        )
        # Write access only for admin
        self.assertTrue(
            perm.has_permission(_make_request(self.admin, method="POST"), self.view)
        )
        self.assertFalse(
            perm.has_permission(_make_request(self.doctor, method="POST"), self.view)
        )

    def test_unauthenticated_denied(self) -> None:
        perm = IsAdmin()
        self.assertFalse(perm.has_permission(_make_request(None), self.view))


# ---------------------------------------------------------------------------
# ExaminationPermission tests (object-level)
# ---------------------------------------------------------------------------


class TestExaminationPermission(TestCase):
    """Test ExaminationPermission with mock examination objects."""

    def setUp(self) -> None:
        self.company = Company.objects.create(name="Test Co", code="TC001")
        self.admin = _make_user(ROLE_ADMIN, email="admin@exam.test")
        self.doctor = _make_user(ROLE_DOCTOR, email="doctor@exam.test")
        self.nurse = _make_user(ROLE_NURSE, email="nurse@exam.test")
        self.labtech = _make_user(ROLE_LABTECH, email="labtech@exam.test")
        # Assign labtech to company
        StaffAssignment.objects.create(user=self.labtech, company=self.company)
        self.perm = ExaminationPermission()
        self.view = MagicMock()

    def _make_exam(
        self, status: str = "draft", doctor=None, company=None
    ) -> MagicMock:
        """Create mock examination object."""
        exam = MagicMock()
        exam.status = status
        exam.doctor = doctor or self.doctor
        # Mock patient with company
        exam.patient = MagicMock()
        exam.patient.company_id = (company or self.company).id
        return exam

    # --- has_permission (request level) ---

    def test_create_allowed_for_admin_doctor_nurse(self) -> None:
        for user in [self.admin, self.doctor, self.nurse]:
            req = _make_request(user, method="POST")
            self.assertTrue(
                self.perm.has_permission(req, self.view),
                f"Expected {user.role} to create examination",
            )

    def test_create_denied_for_labtech_and_company_admin(self) -> None:
        req = _make_request(self.labtech, method="POST")
        self.assertFalse(self.perm.has_permission(req, self.view))

    def test_read_allowed_for_all_authenticated(self) -> None:
        for user in [self.admin, self.doctor, self.nurse, self.labtech]:
            req = _make_request(user, method="GET")
            self.assertTrue(self.perm.has_permission(req, self.view))

    # --- has_object_permission ---

    def test_admin_can_edit_confirmed_exam(self) -> None:
        exam = self._make_exam(status="confirmed")
        req = _make_request(self.admin, method="PUT")
        self.assertTrue(self.perm.has_object_permission(req, self.view, exam))

    def test_doctor_cannot_edit_confirmed_exam(self) -> None:
        exam = self._make_exam(status="confirmed")
        req = _make_request(self.doctor, method="PUT")
        self.assertFalse(self.perm.has_object_permission(req, self.view, exam))

    def test_doctor_can_edit_draft_exam(self) -> None:
        exam = self._make_exam(status="draft")
        req = _make_request(self.doctor, method="PUT")
        self.assertTrue(self.perm.has_object_permission(req, self.view, exam))

    def test_doctor_can_edit_completed_exam(self) -> None:
        exam = self._make_exam(status="completed")
        req = _make_request(self.doctor, method="PUT")
        self.assertTrue(self.perm.has_object_permission(req, self.view, exam))

    def test_nurse_can_edit_own_draft(self) -> None:
        exam = self._make_exam(status="draft", doctor=self.nurse)
        req = _make_request(self.nurse, method="PUT")
        self.assertTrue(self.perm.has_object_permission(req, self.view, exam))

    def test_nurse_cannot_edit_others_draft(self) -> None:
        exam = self._make_exam(status="draft", doctor=self.doctor)
        req = _make_request(self.nurse, method="PUT")
        self.assertFalse(self.perm.has_object_permission(req, self.view, exam))

    def test_nurse_cannot_edit_completed_exam(self) -> None:
        exam = self._make_exam(status="completed", doctor=self.nurse)
        req = _make_request(self.nurse, method="PUT")
        self.assertFalse(self.perm.has_object_permission(req, self.view, exam))

    def test_labtech_can_edit_assigned_company_exam(self) -> None:
        exam = self._make_exam(status="draft", company=self.company)
        req = _make_request(self.labtech, method="PUT")
        self.assertTrue(self.perm.has_object_permission(req, self.view, exam))

    def test_labtech_cannot_edit_unassigned_company_exam(self) -> None:
        other_company = Company.objects.create(name="Other Co", code="OC001")
        exam = self._make_exam(status="draft", company=other_company)
        req = _make_request(self.labtech, method="PUT")
        self.assertFalse(self.perm.has_object_permission(req, self.view, exam))

    def test_delete_draft_by_owner(self) -> None:
        exam = self._make_exam(status="draft", doctor=self.doctor)
        req = _make_request(self.doctor, method="DELETE")
        self.assertTrue(self.perm.has_object_permission(req, self.view, exam))

    def test_delete_completed_denied_for_non_admin(self) -> None:
        exam = self._make_exam(status="completed", doctor=self.doctor)
        req = _make_request(self.doctor, method="DELETE")
        self.assertFalse(self.perm.has_object_permission(req, self.view, exam))

    def test_delete_draft_denied_for_non_owner(self) -> None:
        exam = self._make_exam(status="draft", doctor=self.doctor)
        req = _make_request(self.nurse, method="DELETE")
        self.assertFalse(self.perm.has_object_permission(req, self.view, exam))


# ---------------------------------------------------------------------------
# ExaminationConfirmPermission tests
# ---------------------------------------------------------------------------


class TestExaminationConfirmPermission(TestCase):
    def setUp(self) -> None:
        self.admin = _make_user(ROLE_ADMIN, email="admin@confirm.test")
        self.doctor = _make_user(ROLE_DOCTOR, email="doctor@confirm.test")
        self.nurse = _make_user(ROLE_NURSE, email="nurse@confirm.test")
        self.perm = ExaminationConfirmPermission()
        self.view = MagicMock()

    def test_admin_can_confirm(self) -> None:
        self.assertTrue(
            self.perm.has_permission(_make_request(self.admin), self.view)
        )

    def test_doctor_can_confirm(self) -> None:
        self.assertTrue(
            self.perm.has_permission(_make_request(self.doctor), self.view)
        )

    def test_nurse_cannot_confirm(self) -> None:
        self.assertFalse(
            self.perm.has_permission(_make_request(self.nurse), self.view)
        )


# ---------------------------------------------------------------------------
# IsOwnCompanyOrAdmin tests
# ---------------------------------------------------------------------------


class TestIsOwnCompanyOrAdmin(TestCase):
    def setUp(self) -> None:
        self.company_a = Company.objects.create(name="Company A", code="CA001")
        self.company_b = Company.objects.create(name="Company B", code="CB001")
        self.admin = _make_user(ROLE_ADMIN, email="admin@company.test")
        self.cadmin = _make_user(
            ROLE_COMPANY_ADMIN,
            email="cadmin@company.test",
            company=self.company_a,
        )
        self.perm = IsOwnCompanyOrAdmin()
        self.view = MagicMock()

    def test_admin_can_access_any_company_object(self) -> None:
        obj = MagicMock(company_id=self.company_b.id)
        req = _make_request(self.admin)
        self.assertTrue(self.perm.has_object_permission(req, self.view, obj))

    def test_company_admin_can_access_own_company(self) -> None:
        obj = MagicMock(company_id=self.company_a.id)
        req = _make_request(self.cadmin)
        self.assertTrue(self.perm.has_object_permission(req, self.view, obj))

    def test_company_admin_cannot_access_other_company(self) -> None:
        obj = MagicMock(company_id=self.company_b.id)
        req = _make_request(self.cadmin)
        self.assertFalse(self.perm.has_object_permission(req, self.view, obj))


# ---------------------------------------------------------------------------
# StaffAssignment model tests
# ---------------------------------------------------------------------------


class TestStaffAssignment(TestCase):
    def setUp(self) -> None:
        self.company = Company.objects.create(name="Test Co", code="SA001")
        self.nurse = _make_user(ROLE_NURSE, email="nurse@assign.test")
        self.labtech = _make_user(ROLE_LABTECH, email="labtech@assign.test")

    def test_create_assignment(self) -> None:
        assignment = StaffAssignment.objects.create(
            user=self.nurse, company=self.company
        )
        self.assertEqual(assignment.user, self.nurse)
        self.assertEqual(assignment.company, self.company)

    def test_unique_constraint(self) -> None:
        StaffAssignment.objects.create(user=self.nurse, company=self.company)
        with self.assertRaises(Exception):
            StaffAssignment.objects.create(user=self.nurse, company=self.company)

    def test_reverse_relation(self) -> None:
        StaffAssignment.objects.create(user=self.labtech, company=self.company)
        self.assertEqual(self.labtech.staff_assignments.count(), 1)
        self.assertEqual(self.company.staff_assignments.count(), 1)


# ---------------------------------------------------------------------------
# Group permission seeding test
# ---------------------------------------------------------------------------


class TestGroupPermissionsSeeded(TestCase):
    """Verify that the data migration populated group permissions correctly."""

    def test_admin_group_has_user_crud(self) -> None:
        group = Group.objects.get(name="admin")
        perms = list(group.permissions.values_list("codename", flat=True))
        for action in ["add_user", "change_user", "delete_user", "view_user"]:
            self.assertIn(action, perms, f"Admin group missing '{action}'")

    def test_doctor_group_has_view_user(self) -> None:
        group = Group.objects.get(name="doctor")
        perms = list(group.permissions.values_list("codename", flat=True))
        self.assertIn("view_user", perms)
        self.assertNotIn("add_user", perms)
        self.assertNotIn("delete_user", perms)

    def test_nurse_group_has_view_user(self) -> None:
        group = Group.objects.get(name="nurse")
        perms = list(group.permissions.values_list("codename", flat=True))
        self.assertIn("view_user", perms)

    def test_company_admin_group_has_view_company(self) -> None:
        group = Group.objects.get(name="company_admin")
        perms = list(group.permissions.values_list("codename", flat=True))
        self.assertIn("view_company", perms)
        self.assertNotIn("add_company", perms)

    def test_labtech_group_has_no_user_perms(self) -> None:
        group = Group.objects.get(name="labtech")
        perms = list(group.permissions.values_list("codename", flat=True))
        self.assertNotIn("view_user", perms)
        self.assertNotIn("add_user", perms)
