"""
Permission classes for the department & template engine — Sprint 4.

Per the Sprint 2a matrix:
- Department CRUD: Admin only (CMS role). Clinical staff read-only.
- DepartmentTemplate CRUD: Admin/Doctor create+edit; Nurse/LabTech read-only.
- ExamPackage CRUD: Admin/Doctor create+edit; others read-only.
"""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from core.permissions import (
    CLINICAL_STAFF_ROLES,
    ROLE_ADMIN,
    ROLE_COMPANY_ADMIN,
    ROLE_DOCTOR,
    ROLE_LABTECH,
    ROLE_NURSE,
)


class DepartmentPermission(BasePermission):
    """
    - Read: any authenticated clinical staff member.
    - Create/Update/Delete: admin only.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return user.role in CLINICAL_STAFF_ROLES
        return user.role == ROLE_ADMIN


class TemplatePackagePermission(BasePermission):
    """
    - Read: any authenticated clinical staff member.
    - Create/Update/Delete: admin or doctor.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return user.role in CLINICAL_STAFF_ROLES
        return user.role in {ROLE_ADMIN, ROLE_DOCTOR}


class ExaminationEntryPermission(BasePermission):
    """
    View-level gate for the Examination entry endpoints (Sprint 5).

    - Read (list/retrieve/form): any authenticated clinical staff or
      CompanyAdmin (querysets scope the rows they may see).
    - Create: admin, doctor, or nurse (nurses create drafts).
    - Delete: admin, doctor, or nurse (object rule enforces draft-only).
    - Department data writes / status changes: any medical editor; the
      fine-grained department-category and status rules are enforced in the
      view actions.

    CompanyAdmin is read-only (cannot mutate any medical data).
    """

    CREATE_ROLES = {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE}
    WRITE_ROLES = {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, "labtech"}

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return user.role in CLINICAL_STAFF_ROLES or user.role == ROLE_COMPANY_ADMIN
        if request.method == "POST":
            return user.role in self.CREATE_ROLES
        # PUT/PATCH/DELETE — deeper checks happen at object/action level.
        return user.role in self.WRITE_ROLES

    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True
        role = request.user.role
        if role == ROLE_ADMIN:
            return True
        # Confirmed exams are immutable except by admin.
        if getattr(obj, "status", None) == "confirmed":
            return False
        if request.method == "DELETE":
            # Draft-only deletion enforced in perform_destroy; owner or doctor.
            return obj.status == "draft" and (
                role == ROLE_DOCTOR or obj.doctor_id == request.user.id
            )
        return role in self.WRITE_ROLES


class ImportPermission(BasePermission):
    """
    Permission for Excel import endpoints (Sprint 6).

    - Read (check import status): any authenticated clinical staff.
    - Create (upload import): admin, doctor, nurse, labtech — further
      department-level checks happen in the view.
    """

    IMPORT_ROLES = {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LABTECH}

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return user.role in CLINICAL_STAFF_ROLES
        return user.role in self.IMPORT_ROLES
