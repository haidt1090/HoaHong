"""
Sync scope resolution + pre-sync validation — Phase 8, Sprint 16.

Any examination in scope may be pushed (draft / completed / confirmed).
``validate_scope`` lists pending exams, already-synced exams, and CKS blockers.
Bulk sync ("đồng bộ tất cả") skips exams that previously pushed successfully
for the same environment.
"""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from examinations.models import Examination
from nationalsync.models import SyncJob

SCOPE_COMPANY = "company"
SCOPE_PATIENT = "patient"


class InvalidScope(ValueError):
    """Raised when the requested sync scope is missing required filters."""


def resolve_examinations(
    scope_type: str,
    company_id: Any = None,
    patient_id: Any = None,
    examination_id: Any = None,
) -> QuerySet[Examination]:
    """Return the queryset of examinations matching the sync scope.

    - ``company``: examinations under the company's *active* exam package
      (``CompanyExamPackage.is_active=True``).
    - ``patient``: all examinations of a single (walk-in) patient.
    - Optional ``examination_id`` narrows the queryset to a single exam
      (must still belong to the chosen scope).
    """
    queryset = Examination.objects.select_related("patient")

    if scope_type == SCOPE_COMPANY:
        if not company_id:
            raise InvalidScope("company_id is required for scope_type=company.")
        queryset = queryset.filter(
            company_exam_package__company_id=company_id,
            company_exam_package__is_active=True,
        )
    elif scope_type == SCOPE_PATIENT:
        if not patient_id:
            raise InvalidScope("patient_id is required for scope_type=patient.")
        queryset = queryset.filter(patient_id=patient_id)
    else:
        raise InvalidScope(f"Unknown scope_type: {scope_type!r}")

    if examination_id:
        queryset = queryset.filter(pk=examination_id)
        if not queryset.exists():
            raise InvalidScope(
                "Lượt khám không thuộc phạm vi đã chọn hoặc không tồn tại."
            )

    return queryset.order_by("exam_date", "patient__full_name")


def successfully_synced_ids(environment: str | None) -> set[str]:
    """Examination IDs that completed a successful push for ``environment``."""
    if not environment:
        return set()
    ids: set[str] = set()
    jobs = SyncJob.objects.filter(
        environment=environment,
        status=SyncJob.STATUS_DONE,
    ).only("examination_id", "synced_examination_ids")
    for job in jobs:
        for raw in job.synced_examination_ids or []:
            text = str(raw).strip()
            if text:
                ids.add(text)
        if job.examination_id:
            ids.add(str(job.examination_id))
    return ids


def incomplete_examinations(examinations: QuerySet[Examination]) -> list[Examination]:
    """Deprecated: status no longer blocks sync. Always returns ``[]``."""
    del examinations
    return []


def eligible_examinations(examinations: QuerySet[Examination]) -> list[Examination]:
    """Return every examination in the queryset (any status may sync)."""
    return list(examinations)


def _exam_summary(exam: Examination) -> dict[str, Any]:
    doctor = exam.doctor
    return {
        "id": str(exam.id),
        "patient": exam.patient.full_name,
        "doctor": doctor.display_name if doctor is not None else "",
        "exam_date": exam.exam_date.isoformat(),
        "status": exam.status,
    }


def signature_issues_for_exams(exams: list[Examination]) -> list[str]:
    """No signature blocker.

    ``CKS_NGUOI_KET_LUAN`` stays empty; the doctor signs on the portal.
    The facility USB signature is collected when sync is triggered.
    """
    del exams
    return []


def validate_scope(
    scope_type: str,
    company_id: Any = None,
    patient_id: Any = None,
    examination_id: Any = None,
    environment: str | None = None,
    *,
    skip_already_synced: bool | None = None,
) -> dict[str, Any]:
    """Validate a scope and return eligibility + already-synced summary.

    When ``skip_already_synced`` is true (default for bulk scope without
    ``examination_id``), exams that already pushed successfully for
    ``environment`` are listed under ``already_synced`` and excluded from
    ``eligible_exams``. Single-exam sync keeps them eligible so the admin can
    re-push explicitly.
    """
    if skip_already_synced is None:
        skip_already_synced = examination_id is None

    queryset = resolve_examinations(
        scope_type,
        company_id=company_id,
        patient_id=patient_id,
        examination_id=examination_id,
    ).select_related("doctor")
    all_exams = list(queryset)
    synced_ids = successfully_synced_ids(environment) if skip_already_synced else set()

    already_synced = [exam for exam in all_exams if str(exam.id) in synced_ids]
    pending = [exam for exam in all_exams if str(exam.id) not in synced_ids]

    doctor_ids = {exam.doctor_id for exam in pending if exam.doctor_id}
    return {
        "total": len(all_exams),
        "eligible": len(pending),
        "eligible_exams": [_exam_summary(exam) for exam in pending],
        "already_synced_count": len(already_synced),
        "already_synced": [_exam_summary(exam) for exam in already_synced],
        # Kept empty for API compatibility — status no longer blocks sync.
        "incomplete": [],
        "signature_issues": signature_issues_for_exams(pending),
        "concluding_doctor_count": len(doctor_ids),
    }
