"""Examination creation helpers used by import and other entry points."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from django.utils import timezone

from accounts.models import Company, CompanyExamPackage
from examinations.formula_evaluator import evaluate_computed_fields
from examinations.models import DepartmentResult, Examination
from patients.models import Patient


def spawn_seeded_department_results(examination: Examination) -> None:
    """Create missing department rows and seed empty fields (default, then random).

    Formula fields are evaluated after numeric/text seeds so BMI/IF see real values.
    """
    package = examination.exam_package
    if package is None:
        return

    bindings = list(
        package.package_departments.select_related("department", "template").all()
    )
    existing = set(
        DepartmentResult.objects.filter(examination=examination).values_list(
            "department_id", "template_id"
        )
    )
    to_create = [
        DepartmentResult(
            examination=examination,
            department=binding.department,
            template=binding.template,
            template_snapshot=binding.template.fields_config if binding.template else [],
        )
        for binding in bindings
        if (binding.department_id, binding.template_id) not in existing
    ]
    results = (
        list(DepartmentResult.objects.bulk_create(to_create)) if to_create else []
    )
    if not results:
        results = list(examination.department_results.all())

    for result in results:
        result.examination = examination
        result._sync_values({}, randomize=True)
        snapshot = result.template_snapshot or []
        gender = examination.patient.gender if examination.patient_id else None
        computed = evaluate_computed_fields(snapshot, result.data, gender=gender)
        if computed != result.data:
            result._sync_values(computed, randomize=False)

    examination.recompute_status()


def create_seeded_examinations_for_patients(
    patients: Sequence[Patient],
    *,
    company: Company,
    exam_date: date | None = None,
    doctor: Any = None,
) -> int:
    """Create one examination per active company package for each new patient.

    Skips packages that are inactive, and does not overwrite an exam that
    already exists for ``(patient, exam_package)``.
    """
    if not patients:
        return 0

    ceps = list(
        CompanyExamPackage.objects.filter(
            company=company,
            is_active=True,
            exam_package__is_active=True,
        ).select_related("exam_package")
    )
    if not ceps:
        return 0

    patient_ids = [p.pk for p in patients if p.pk]
    package_ids = [cep.exam_package_id for cep in ceps]
    existing = set(
        Examination.objects.filter(
            patient_id__in=patient_ids,
            exam_package_id__in=package_ids,
        ).values_list("patient_id", "exam_package_id")
    )

    when = exam_date or timezone.localdate()
    to_create: list[Examination] = []
    patient_by_id = {p.pk: p for p in patients}
    for patient in patients:
        if not patient.pk:
            continue
        for cep in ceps:
            if (patient.pk, cep.exam_package_id) in existing:
                continue
            pkg = cep.exam_package
            to_create.append(
                Examination(
                    patient=patient,
                    company_exam_package=cep,
                    exam_package=pkg,
                    exam_type=pkg.exam_type,
                    exam_date=when,
                    status=Examination.STATUS_DRAFT,
                    doctor=doctor,
                )
            )

    if not to_create:
        return 0

    created = list(Examination.objects.bulk_create(to_create, batch_size=500))
    pkg_by_id = {cep.exam_package_id: cep.exam_package for cep in ceps}
    for exam in created:
        exam.patient = patient_by_id[exam.patient_id]
        exam.exam_package = pkg_by_id.get(exam.exam_package_id) or exam.exam_package
        spawn_seeded_department_results(exam)
    return len(created)
