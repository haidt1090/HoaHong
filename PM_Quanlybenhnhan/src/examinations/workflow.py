"""
Examination status workflow — Phase 2, Sprint 5.

Transitions::

    draft ──(auto, all departments filled)──▶ completed ──▶ confirmed
                                              ▲            │
                                              └────────────┘  (reopen by admin)

Rules:
- ``draft`` → ``completed``: automatic — occurs when all DepartmentResult fields
  are filled (via :meth:`Examination.recompute_status`).
- ``completed`` → ``confirmed``: doctor or admin only.
- ``confirmed`` → ``completed``: admin only (re-open locked exam).
- Only ``draft`` exams are deletable.
"""

from __future__ import annotations

from core.permissions import ROLE_ADMIN, ROLE_DOCTOR
from examinations.models import Examination

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    Examination.STATUS_DRAFT: set(),
    Examination.STATUS_COMPLETED: {Examination.STATUS_CONFIRMED},
    Examination.STATUS_CONFIRMED: {Examination.STATUS_COMPLETED},
}


class WorkflowError(Exception):
    """Raised when a status transition is not allowed."""


def can_transition(current: str, target: str) -> bool:
    """Return True if ``current`` → ``target`` is a valid transition."""
    return target in ALLOWED_TRANSITIONS.get(current, set())


def can_user_transition(role: str, current: str, target: str) -> bool:
    """
    Return True if a user with ``role`` may perform the transition.

    - Confirming (→ confirmed): doctor or admin.
    - Reopening a confirmed exam (→ completed): admin only.
    """
    if role == ROLE_ADMIN:
        return True
    if role != ROLE_DOCTOR:
        return False
    return current != Examination.STATUS_CONFIRMED


def transition(examination: Examination, target: str, role: str) -> Examination:
    """
    Apply a status transition, enforcing the workflow rules.

    Raises :class:`WorkflowError` on an invalid or unauthorized transition.

    Note: ``draft`` → ``completed`` is not managed through this function;
    it happens automatically when data is saved.
    """
    current = examination.status
    if current == target:
        return examination
    if not can_transition(current, target):
        raise WorkflowError(
            f"Không thể chuyển trạng thái từ '{current}' sang '{target}'."
        )
    if not can_user_transition(role, current, target):
        raise WorkflowError("Bạn không có quyền thực hiện chuyển trạng thái này.")
    examination.status = target
    examination.save(update_fields=["status", "version", "updated_at"])
    return examination
