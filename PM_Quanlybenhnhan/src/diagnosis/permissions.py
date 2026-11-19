"""Diagnosis app permissions — Admin only for write, clinical staff read."""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from core.permissions import CLINICAL_STAFF_ROLES, ROLE_ADMIN


class DiagnosisKeywordPermission(BasePermission):
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
