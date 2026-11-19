"""
Role-based permission classes for DRF views.

Sprint 2a — shared across all apps.
"""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

# ---------------------------------------------------------------------------
# Role constants (match accounts.models.User.ROLE_CHOICES)
# ---------------------------------------------------------------------------

ROLE_ADMIN = "admin"
ROLE_DOCTOR = "doctor"
ROLE_NURSE = "nurse"
ROLE_LABTECH = "labtech"
ROLE_COMPANY_ADMIN = "company_admin"

# Convenience groups
CLINICAL_STAFF_ROLES = {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LABTECH}
MEDICAL_EDITORS = {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LABTECH}


# ---------------------------------------------------------------------------
# Department-level access control (Sprint 2a — department-based RBAC)
# ---------------------------------------------------------------------------
#
# Permissions are enforced at the DepartmentResult level (one row per
# department of an examination) rather than by locking JSONField keys.
#
# There are two complementary mechanisms:
#   1. Category-based (preferred): each Department belongs to a category
#      ("clinical" or "para_clinical"). Roles map to allowed categories.
#   2. Explicit code list (fallback): a role may be granted access to a
#      specific set of department codes. "*" grants all departments.

DEPARTMENT_CATEGORY_CLINICAL = "clinical"
DEPARTMENT_CATEGORY_PARACLINICAL = "para_clinical"

WILDCARD = "*"

# Role → allowed department categories. WILDCARD means all categories.
ROLE_DEPARTMENT_CATEGORY_ACCESS: dict[str, object] = {
    ROLE_NURSE: {DEPARTMENT_CATEGORY_CLINICAL},
    ROLE_LABTECH: {DEPARTMENT_CATEGORY_PARACLINICAL},
    ROLE_DOCTOR: WILDCARD,
    ROLE_ADMIN: WILDCARD,
}

# Role → allowed department codes (explicit fallback per the sprint doc).
# WILDCARD ("*") grants all department codes.
ROLE_DEPARTMENT_ACCESS: dict[str, list[str]] = {
    ROLE_NURSE: [
        "kham_lam_sang",
        "mat",
        "da_lieu",
        "tmh",
        "rang_ham_mat",
    ],
    ROLE_LABTECH: [
        "xet_nghiem",
        "xet_nghiem_mau",
        "xet_nghiem_nuoc_tieu",
        "x_quang",
        "sieu_am",
    ],
    ROLE_DOCTOR: [WILDCARD],
    ROLE_ADMIN: [WILDCARD],
}


def can_edit_department_category(role: str, category: str | None) -> bool:
    """Return True if the role may edit departments of the given category."""
    allowed = ROLE_DEPARTMENT_CATEGORY_ACCESS.get(role)
    if allowed is None:
        return False
    if allowed == WILDCARD:
        return True
    return category in allowed


def can_edit_department_code(role: str, code: str | None) -> bool:
    """Return True if the role may edit the department with the given code."""
    allowed = ROLE_DEPARTMENT_ACCESS.get(role, [])
    return WILDCARD in allowed or (code is not None and code in allowed)


def can_edit_department(role: str, department: Any) -> bool:
    """
    Return True if the role may edit the given department object.

    Prefers the department's ``category`` attribute; falls back to its
    ``code`` when no category is available.
    """
    if role in (ROLE_ADMIN, ROLE_DOCTOR):
        return True
    category = getattr(department, "category", None)
    if category is not None:
        return can_edit_department_category(role, category)
    code = getattr(department, "code", None)
    return can_edit_department_code(role, code)


def get_editable_department_codes(role: str) -> list[str]:
    """
    Return the list of department codes editable by the role.

    Returns ``["*"]`` for roles with access to all departments.
    """
    return list(ROLE_DEPARTMENT_ACCESS.get(role, []))


# ---------------------------------------------------------------------------
# Base role permission classes
# ---------------------------------------------------------------------------


class IsAdmin(BasePermission):
    """Allow only users with role=admin."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == ROLE_ADMIN
        )


class IsDoctor(BasePermission):
    """Allow only users with role=doctor."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == ROLE_DOCTOR
        )


class IsNurse(BasePermission):
    """Allow only users with role=nurse."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == ROLE_NURSE
        )


class IsLabTech(BasePermission):
    """Allow only users with role=labtech."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == ROLE_LABTECH
        )


class IsCompanyAdmin(BasePermission):
    """Allow only users with role=company_admin."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == ROLE_COMPANY_ADMIN
        )


class IsClinicalStaff(BasePermission):
    """Allow admin, doctor, nurse, or labtech — anyone who works in the clinic."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in CLINICAL_STAFF_ROLES
        )


class IsAdminOrDoctor(BasePermission):
    """Allow admin or doctor."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {ROLE_ADMIN, ROLE_DOCTOR}
        )


class IsAdminOrReadOnly(BasePermission):
    """Allow admin full access; others read-only."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role == ROLE_ADMIN


# ---------------------------------------------------------------------------
# Object-level permission for Examination (ready for examinations app)
# ---------------------------------------------------------------------------


class ExaminationPermission(BasePermission):
    """
    Object-level permission for Examination model.

    - Read: any authenticated user (filtered at queryset level per role).
    - Create: admin, doctor, nurse.
    - Edit: depends on role + exam status + field ownership.
    - Confirm: admin, doctor only.
    - Delete: admin or owner of a draft exam.
    """

    # Roles allowed to create examinations
    CREATE_ROLES = {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE}

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.method == "POST":
            return request.user.role in self.CREATE_ROLES
        # PUT/PATCH/DELETE handled at object level
        return request.user.role in MEDICAL_EDITORS

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        role = user.role

        # Admin can do anything
        if role == ROLE_ADMIN:
            return True

        # Confirmed exams are immutable for non-admin
        if getattr(obj, "status", None) == "confirmed":
            return False

        # DELETE: only drafts, by owner or admin
        if request.method == "DELETE":
            return obj.status == "draft" and obj.doctor == user

        # Doctor can edit any non-confirmed exam
        if role == ROLE_DOCTOR:
            return True

        # Nurse can only edit own drafts
        if role == ROLE_NURSE:
            return obj.status == "draft" and obj.doctor == user

        # LabTech can only edit assigned exams
        if role == ROLE_LABTECH:
            # Check via StaffAssignment or direct assignment
            if hasattr(user, "staff_assignments"):
                assigned_companies = user.staff_assignments.values_list(
                    "company_id", flat=True
                )
                patient = getattr(obj, "patient", None)
                if patient and patient.company_id in assigned_companies:
                    return True
            return False

        return False


class ExaminationConfirmPermission(BasePermission):
    """Only admin and doctor can confirm an examination."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {ROLE_ADMIN, ROLE_DOCTOR}
        )


# ---------------------------------------------------------------------------
# Department-level permission (Sprint 2a — per-department write control)
# ---------------------------------------------------------------------------


class DepartmentResultPermission(BasePermission):
    """
    Enforce department-level write access on DepartmentResult rows.

    - Read: any authenticated clinical staff member.
    - Write: only if the user's role may edit the target department
      (by category, falling back to department code).

    The department is resolved in this order:
      1. ``view.get_department()`` (if the view exposes it), or
      2. ``obj.department`` at the object level.

    The conclusion is doctor/admin only and is expected to be guarded
    separately (e.g. via ``ExaminationConfirmPermission`` or a dedicated
    conclusion endpoint).
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return request.user.role in CLINICAL_STAFF_ROLES
        if request.user.role not in MEDICAL_EDITORS:
            return False

        # If the view can resolve a department up-front, check it now.
        department = None
        get_department = getattr(view, "get_department", None)
        if callable(get_department):
            department = get_department()
        if department is not None:
            return can_edit_department(request.user.role, department)
        # Otherwise defer to object-level check.
        return True

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        if request.method in SAFE_METHODS:
            return request.user.role in CLINICAL_STAFF_ROLES

        role = request.user.role
        if role == ROLE_ADMIN:
            return True

        # A confirmed parent examination is immutable for non-admin.
        examination = getattr(obj, "examination", None)
        if getattr(examination, "status", None) == "confirmed":
            return False

        department = getattr(obj, "department", None)
        if department is None:
            department = obj  # obj may itself be a Department
        return can_edit_department(role, department)


# ---------------------------------------------------------------------------
# Company-scoped permission (for CompanyAdmin role)
# ---------------------------------------------------------------------------


class IsOwnCompanyOrAdmin(BasePermission):
    """
    CompanyAdmin can only access objects belonging to their company.
    Admin has full access.
    """

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        user = request.user
        if user.role == ROLE_ADMIN:
            return True
        if user.role == ROLE_COMPANY_ADMIN:
            # Object must have a company or patient.company reference
            obj_company = getattr(obj, "company_id", None) or getattr(
                getattr(obj, "patient", None), "company_id", None
            )
            return obj_company == user.company_id
        return False
