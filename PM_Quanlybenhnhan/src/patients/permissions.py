"""
Permission classes for the patients and company registry.

Follows the Sprint 2a permission matrix:

- Patient CRUD: Admin full; Doctor/Nurse view_all; LabTech view_assigned;
  CompanyAdmin view_own_company.
- Company CRUD: Admin full; Doctor view; others none.

Queryset-level scoping (view_all vs view_assigned vs view_own_company) is
handled in the viewset's ``get_queryset``; these classes gate the HTTP verb.
"""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from core.permissions import (
    ROLE_ADMIN,
    ROLE_COMPANY_ADMIN,
    ROLE_DOCTOR,
    ROLE_LABTECH,
    ROLE_NURSE,
)

# Roles allowed to read the patient registry.
PATIENT_VIEW_ROLES = {
    ROLE_ADMIN,
    ROLE_DOCTOR,
    ROLE_NURSE,
    ROLE_LABTECH,
    ROLE_COMPANY_ADMIN,
}


class PatientPermission(BasePermission):
    """
    - Read: admin, doctor, nurse, labtech, company_admin (queryset-scoped).
    - Create/Update/Delete: admin only.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return user.role in PATIENT_VIEW_ROLES
        return user.role == ROLE_ADMIN

    def has_object_permission(
        self, request: Request, view: APIView, obj: object
    ) -> bool:
        user = request.user
        if request.method in SAFE_METHODS:
            # Object visibility is enforced by get_queryset scoping.
            return True
        return user.role == ROLE_ADMIN


class CompanyPermission(BasePermission):
    """
    - Read: admin, doctor.
    - Create/Update/Delete: admin only.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return user.role in {ROLE_ADMIN, ROLE_DOCTOR}
        return user.role == ROLE_ADMIN
