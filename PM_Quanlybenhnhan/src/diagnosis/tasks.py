"""
Scheduled diagnosis scan — Sprint 7.

Fills ``work_fitness`` / ``disease`` / ``consultation`` for examinations that
the doctor has not yet concluded, by running the keyword-matching diagnosis
engine over each examination's aggregated findings.  Auto-filled records are
marked ``auto_diagnosed=True`` so the frontend can flag them for review;
the doctor can still overwrite anything manually.
"""

from __future__ import annotations

import logging

from celery import shared_task

from diagnosis.services import aggregate_findings, match_diagnosis
from examinations.models import Examination

logger = logging.getLogger(__name__)


def _is_unconcluded(exam: Examination) -> bool:
    """True if the exam still needs an automatic conclusion.

    An exam is eligible when the doctor has not set a fitness verdict yet
    (``work_fitness`` is still ``pending``) AND no diseases were attached AND
    no consultation was written.  We deliberately never overwrite existing
    doctor-authored data.
    """
    return (
        exam.work_fitness == "pending"
        and not exam.disease.strip()
        and not exam.consultation.strip()
    )


def _apply_diagnosis(exam: Examination) -> bool:
    """Run diagnosis and persist results.  Returns True if anything changed."""
    findings = aggregate_findings(exam, skip_known_keywords=False)
    matches = match_diagnosis(findings) if findings.strip() else []

    changed = False

    # Bệnh mắc: join matched disease names (dedupe).
    seen: list[str] = []
    for m in matches:
        name = m.get("disease_name", "").strip()
        if name and name not in seen:
            seen.append(name)
    benh_mac = ", ".join(seen)
    if benh_mac and not exam.disease.strip():
        exam.disease = benh_mac
        changed = True

    # Fill consultation from conclusion templates.
    templates = [
        m["conclusion_template"].strip()
        for m in matches
        if m.get("conclusion_template", "").strip()
    ]
    if templates and not exam.consultation.strip():
        exam.consultation = ", ".join(templates)
        changed = True

    # Auto fitness: unfit when any matched keyword is classification>=4 (Loại IV/V),
    # otherwise fit.
    if exam.work_fitness == "pending":
        if any(m["classification"] is not None and m["classification"] >= 4 for m in matches):
            exam.work_fitness = "unfit"
        else:
            exam.work_fitness = "fit"
        changed = True

    # Store the classification number for fast report rendering.
    classification = _classification_number(matches)
    if exam.classification != classification:
        exam.classification = classification
        changed = True

    if changed:
        exam.auto_diagnosed = True
        exam.save()
    return changed


def _classification_number(matches: list[dict[str, Any]]) -> int:
    """Most severe classification: 5 (Loại V) > 4 > 3 > 2 > 1; default 1 (Loại I)."""
    classifications = {m["classification"] for m in matches}
    for level in (5, 4, 3, 2, 1):
        if level in classifications:
            return level
    return 1


@shared_task
def scan_diagnosis_task(limit: int = 500) -> dict[str, int]:
    """Scan unconcluded exams and auto-fill their diagnosis conclusions.

    Returns a small stats dict ``{"scanned", "filled"}``.
    """
    exams = list(
        Examination.objects.select_related("patient")
        .prefetch_related(
            "department_results__values",
            "department_results__department",
        )
        .filter(status__in=["completed", "confirmed"])
        .order_by("-exam_date")[:limit]
    )

    filled = 0
    scanned = 0
    for exam in exams:
        if not _is_unconcluded(exam):
            continue
        scanned += 1
        try:
            if _apply_diagnosis(exam):
                filled += 1
        except Exception:
            logger.exception("Diagnosis scan failed for examination %s", exam.id)

    logger.info("Diagnosis scan: scanned=%d filled=%d", scanned, filled)
    return {"scanned": scanned, "filled": filled}


def run_package_diagnosis(company_exam_package) -> int:
    """Run diagnosis on every unconcluded exam in a company exam package.

    Used by report generation so reports always reflect up-to-date conclusions
    even for examinations the doctor hasn't concluded yet (the results are
    persisted, mirroring the scheduled ``scan_diagnosis_task``).

    Returns the number of examinations whose diagnosis was filled.
    """
    exams = list(
        Examination.objects.filter(
            company_exam_package=company_exam_package,
            status__in=["completed", "confirmed"],
        ).prefetch_related(
            "department_results__values",
            "department_results__department",
        )
    )

    filled = 0
    for exam in exams:
        if not _is_unconcluded(exam):
            continue
        try:
            if _apply_diagnosis(exam):
                filled += 1
        except Exception:
            logger.exception("Diagnosis failed for examination %s", exam.id)

    if filled:
        logger.info("Package diagnosis: filled=%d for cep %s", filled, company_exam_package.id)
    return filled
