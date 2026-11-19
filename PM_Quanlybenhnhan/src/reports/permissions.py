"""
Permission classes for the reports app (Sprint 9a).

Report templates contain author-supplied Django template source, which is a
code-execution surface (filters, attribute traversal). Editing is therefore
restricted to admins; everyone else on clinical staff gets read access so the
generation UI can list templates in a dropdown.
"""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from core.permissions import CLINICAL_STAFF_ROLES, ROLE_ADMIN, ROLE_COMPANY_ADMIN


class ReportTemplatePermission(BasePermission):
    """
    - Read: any authenticated clinical staff member.
    - Create/Update/Delete: admin only (template source is executable).
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return user.role in CLINICAL_STAFF_ROLES
        return user.role == ROLE_ADMIN


class ReportPermission(BasePermission):
    """
    - Read/generate: clinical staff, plus CompanyAdmin for their own company.
    - Delete: admin only.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method == "DELETE":
            return user.role == ROLE_ADMIN
        return user.role in CLINICAL_STAFF_ROLES or user.role == ROLE_COMPANY_ADMIN

    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        user = request.user
        if user.role == ROLE_ADMIN:
            return True
        if user.role == ROLE_COMPANY_ADMIN:
            return obj.company_id == user.company_id
        return user.role in CLINICAL_STAFF_ROLES
