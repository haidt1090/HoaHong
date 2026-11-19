"""
Celery tasks for Excel import — Sprint 6.

Handles async processing of large Excel imports (>100 rows).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from celery import shared_task
from django.utils import timezone
from core.permissions import ROLE_ADMIN

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def process_excel_import(
    self,
    import_job_id: str,
    department_id: str,
    exam_date_str: str,
    file_path: str,
    company_id: str | None = None,
    exam_package_id: str | None = None,
) -> dict[str, Any]:
    """
    Process an Excel import job asynchronously.

    Args:
        import_job_id: UUID of the ImportJob record
        department_id: UUID of the department being imported
        exam_date_str: ISO date string for the exam date
        file_path: Path to the uploaded Excel file
        company_id: Optional UUID of the company (filters patients)
        exam_package_id: Optional UUID of the exam package
    """
    from examinations.models import (
        Department,
        DepartmentResult,
        DepartmentTemplate,
        Examination,
        ImportJob,
    )
    from examinations.excel_utils import parse_department_import
    from patients.models import Patient
    from accounts.models import CompanyExamPackage

    # Import job tracking
    job = ImportJob.objects.get(pk=import_job_id)
    job.status = ImportJob.STATUS_PROCESSING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at", "updated_at"])

    try:
        # Read file
        with open(file_path, "rb") as f:
            file_content = f.read()

        department = Department.objects.get(pk=department_id)

        template = (
            DepartmentTemplate.objects.filter(
                department=department,
                is_active=True,
            )
            .order_by("-version")
            .first()
        )

        if not template:
            job.status = ImportJob.STATUS_FAILED
            job.errors = [
                {
                    "message": f"Không tìm thấy template active cho khoa {department.name}"
                }
            ]
            job.completed_at = timezone.now()
            job.save(update_fields=["status", "errors", "completed_at", "updated_at"])
            return {"status": "failed", "error": "No active template"}

        fields_config = template.fields_config
        headers, rows = parse_department_import(file_content, fields_config)

        total_rows = len(rows)
        success_count = 0
        updated_count = 0
        skipped_count = 0
        errors: list[dict[str, Any]] = []

        exam_date = date.fromisoformat(exam_date_str)
        user = job.created_by

        for row in rows:
            emp_code = str(row.get("employee_code", "")).strip()
            row_num = row.get("_row", 0)

            if not emp_code:
                errors.append(
                    {
                        "row": row_num,
                        "employee_code": "",
                        "message": "Mã nhân viên trống",
                    }
                )
                skipped_count += 1
                continue

            patient_qs = Patient.objects.filter(employee_code=emp_code, is_active=True)
            if company_id:
                patient_qs = patient_qs.filter(company_id=company_id)
            patient = patient_qs.first()

            if not patient:
                errors.append(
                    {
                        "row": row_num,
                        "employee_code": emp_code,
                        "message": f"Không tìm thấy bệnh nhân với mã '{emp_code}'",
                    }
                )
                skipped_count += 1
                continue

            examination = Examination.objects.filter(
                patient=patient,
                exam_package_id=exam_package_id,
            ).first()

            if examination is None:
                if not exam_package_id:
                    errors.append(
                        {
                            "row": row_num,
                            "employee_code": emp_code,
                            "message": "Cần chọn gói khám để tạo phiếu khám mới.",
                        }
                    )
                    skipped_count += 1
                    continue

                cep, _ = CompanyExamPackage.objects.get_or_create(
                    company_id=company_id or patient.company_id,
                    exam_package_id=exam_package_id,
                    defaults={"pricing_mode": "package_total", "total_employees": 0},
                )

                from examinations.models import ExamPackage

                exam_package = ExamPackage.objects.get(pk=exam_package_id)

                examination = Examination.objects.create(
                    patient=patient,
                    company_exam_package=cep,
                    exam_package=exam_package,
                    exam_type=exam_package.exam_type,
                    exam_date=exam_date,
                    status=Examination.STATUS_DRAFT,
                    doctor=user,
                )
                # Spawn all DepartmentResults from the package
                _spawn_department_results(examination)
            else:
                _spawn_department_results(examination)
            if examination.status != Examination.STATUS_COMPLETED or (
                user and user.role == ROLE_ADMIN
            ):
                # Status auto-computed by DepartmentResult.save() → recompute_status()
                examination.doctor = user
                examination.save(
                        update_fields=["doctor", "version", "updated_at"]
                    )

            dept_result, created = DepartmentResult.objects.get_or_create(
                examination=examination,
                department=department,
                defaults={"template_snapshot": fields_config},
            )

            imported_data = {
                k: v for k, v in row.items() if k not in ("employee_code", "_row")
            }
            dept_result.apply_imported_values(imported_data, fields_config)
            dept_result.completed_by = user
            dept_result.completed_at = timezone.now()
            dept_result.save(
                update_fields=[
                    "completed_by",
                    "completed_at",
                    "version",
                    "updated_at",
                ]
            )

            if created:
                success_count += 1
            else:
                updated_count += 1

        job.total_rows = total_rows
        job.success_count = success_count
        job.updated_count = updated_count
        job.skipped_count = skipped_count
        job.errors = errors
        job.status = ImportJob.STATUS_COMPLETED
        job.completed_at = timezone.now()
        job.save(
            update_fields=[
                "total_rows",
                "success_count",
                "updated_count",
                "skipped_count",
                "errors",
                "status",
                "completed_at",
                "updated_at",
            ]
        )

        return {
            "status": "completed",
            "total_rows": total_rows,
            "success_count": success_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "errors": errors,
        }

    except Exception as exc:
        logger.exception("Import job %s failed", import_job_id)
        job.status = ImportJob.STATUS_FAILED
        job.errors = [{"message": f"Lỗi xử lý: {exc}"}]
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "errors", "completed_at", "updated_at"])
        return {"status": "failed", "error": str(exc)}


@shared_task(bind=True, max_retries=2)
def process_excel_export(
    self,
    export_job_id: str,
    company_id: str,
    exam_package_id: str,
    department_id: str,
    exam_date_str: str | None = None,
    mode: str = "all",
) -> dict[str, Any]:
    """
    Generate a pre-populated Excel export for a company's employees.

    Results come from the examination tied to ``exam_package_id``
    (the company's active package), not from ``exam_date``.
    ``exam_date_str`` is accepted for Celery backward compatibility and ignored.
    """
    from django.db.models import Prefetch
    from django.utils import timezone

    from accounts.models import Company
    from examinations.excel_utils import generate_department_export
    from examinations.models import (
        Department,
        DepartmentResult,
        Examination,
        ExamPackage,
        ExamPackageDepartment,
        ExportJob,
    )
    from patients.models import Patient

    del exam_date_str  # Export is scoped by package, not by calendar date.

    export_job = ExportJob.objects.get(pk=export_job_id)
    export_job.status = ExportJob.STATUS_PROCESSING
    export_job.started_at = timezone.now()
    export_job.save(update_fields=["status", "started_at", "updated_at"])

    try:
        company = Company.objects.get(pk=company_id)
        department = Department.objects.get(pk=department_id)
        exam_package = ExamPackage.objects.get(pk=exam_package_id)
        binding = (
            ExamPackageDepartment.objects.filter(
                exam_package_id=exam_package_id,
                department=department,
            )
            .select_related("template")
            .first()
        )
        template = binding.template if binding else None
        if not template:
            raise ValueError(
                f"Không tìm thấy mẫu nhập liệu cho khoa {department.name} "
                f"trong gói {exam_package.name}."
            )

        fields_config = template.fields_config

        patients = Patient.objects.filter(company=company, is_active=True)

        if mode == "pending":
            completed_patient_ids = set(
                DepartmentResult.objects.filter(
                    department=department,
                    template=template,
                    completed_at__isnull=False,
                    examination__exam_package_id=exam_package_id,
                ).values_list("examination__patient_id", flat=True)
            )
            patients = patients.exclude(id__in=completed_patient_ids)

        patients = patients.order_by("employee_code")
        patient_list = list(patients)

        total_patients = len(patient_list)
        export_job.total_progress = total_patients
        export_job.save(update_fields=["total_progress", "updated_at"])

        exams_by_patient = {
            exam.patient_id: exam
            for exam in Examination.objects.filter(
                exam_package_id=exam_package_id,
                patient_id__in=[p.id for p in patient_list],
            ).prefetch_related(
                Prefetch(
                    "department_results",
                    queryset=DepartmentResult.objects.filter(
                        department=department,
                        template=template,
                    ).prefetch_related("values"),
                )
            )
        }

        employees: list[dict[str, Any]] = []
        for patient in patient_list:
            emp_data: dict[str, Any] = {
                "employee_code": patient.employee_code,
                "full_name": patient.full_name,
                "data": {},
            }
            exam = exams_by_patient.get(patient.id)
            if exam:
                merged: dict[str, Any] = {}
                for dr in exam.department_results.all():
                    if dr.data:
                        merged.update(dr.data)
                emp_data["data"] = merged
            employees.append(emp_data)

        export_job.current_progress = total_patients
        export_job.save(update_fields=["current_progress", "updated_at"])

        sheet_name = f"{department.name[:31]}"
        content = generate_department_export(
            fields_config=fields_config,
            employees=employees,
            sheet_name=sheet_name,
        )

        from django.core.files.base import ContentFile
        from django.utils.text import get_valid_filename

        filename = f"{company.name}_{exam_package.name}_{template.name}_result.xlsx"
        safe_filename = get_valid_filename(filename)
        export_job.file.save(
            safe_filename,
            ContentFile(content),
            save=True,
        )

        export_job.status = ExportJob.STATUS_COMPLETED
        export_job.completed_at = timezone.now()
        export_job.current_progress = total_patients
        export_job.total_progress = total_patients
        export_job.save(
            update_fields=[
                "status",
                "completed_at",
                "current_progress",
                "total_progress",
                "updated_at",
            ]
        )

        return {
            "status": "completed",
            "progress": {"current": total_patients, "total": total_patients},
        }

    except Exception as exc:
        logger.exception("Export job %s failed", export_job_id)
        export_job.status = ExportJob.STATUS_FAILED
        export_job.error_message = str(exc)
        export_job.completed_at = timezone.now()
        export_job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
        return {"status": "failed", "error": str(exc)}



def _spawn_department_results(examination: Examination) -> None:
    """Create one DepartmentResult per department/template in the package."""
    from examinations.models import (
        DepartmentResult,
        DepartmentResultValue,
        _to_decimal,
        _value_as_text,
    )

    package = examination.exam_package
    if package is None:
        return
    gender = examination.patient.gender if examination.patient_id else None
    bindings = (
        package.package_departments.select_related("department", "template")
        .prefetch_related("template__fields")
        .all()
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
            template_snapshot=binding.template.fields_config,
        )
        for binding in bindings
        if (binding.department_id, binding.template_id) not in existing
    ]
    if not to_create:
        return

    results = DepartmentResult.objects.bulk_create(to_create)
    values_to_create = []
    for result_obj in results:
        binding = next(
            b for b in bindings if str(b.template_id) == str(result_obj.template_id)
        )
        for field in binding.template.fields.all():
            default = field.resolve_default_value(gender)
            if default:
                values_to_create.append(
                    DepartmentResultValue(
                        result=result_obj,
                        field_key=field.key,
                        value_number=_to_decimal(default, field.field_type),
                        value_text=_value_as_text(default, field.field_type),
                    )
                )
    if values_to_create:
        DepartmentResultValue.objects.bulk_create(values_to_create)
