"""
DEPRECATED — see core/permissions.py for department-category access control.

Field-level locking (FIELDS_ROLE_MAP + FieldLockingMixin) is superseded by
department-level permission based on Department.category.

Use core.permissions.DepartmentResultPermission instead.
"""

from __future__ import annotations

from core.exceptions import PermissionDenied

# ---------------------------------------------------------------------------
# Deprecated — kept only for reference; not used by any view.
# ---------------------------------------------------------------------------

FIELD_ROLE_MAP: dict[str, list[str]] = {}  # clear; no longer applicable


class FieldLockingMixin:
    """
    DEPRECATED — do not use.

    The department-based architecture replaced per-JSONField locking
    with per-DepartmentResult locking. Use ``DepartmentResultPermission``
    from ``core.permissions`` instead.
    """

    field_role_map: dict[str, list[str]] = {}
    field_lock_strict: bool = False

    def _deprecated_warning(self) -> None:
        import warnings
        warnings.warn(
            "FieldLockingMixin is deprecated. "
            "Use core.permissions.DepartmentResultPermission instead.",
            DeprecationWarning,
            stacklevel=3,
        )

    def validate(self, attrs: dict) -> dict:
        self._deprecated_warning()
        return attrs
