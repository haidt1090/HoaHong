from __future__ import annotations

from datetime import date

from django.db.models import Q, QuerySet
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from core.permissions import (
    ROLE_ADMIN,
    ROLE_COMPANY_ADMIN,
    ROLE_DOCTOR,
    ROLE_LABTECH,
    ROLE_NURSE,
    can_edit_department,
)
from diagnosis.services import aggregate_findings, match_diagnosis
from examinations import workflow
from examinations.excel_utils import (
    generate_department_template,
    parse_department_import,
)
from examinations.formula_evaluator import evaluate_computed_fields
from examinations.models import (
    Department,
    DepartmentResult,
    DepartmentResultValue,
    DepartmentTemplate,
    Examination,
    ExamPackage,
    ExportJob,
    ImportJob,
    _to_decimal,
    _value_as_text,
)
from examinations.permissions import (
    DepartmentPermission,
    ExaminationEntryPermission,
    ImportPermission,
    TemplatePackagePermission,
)
from examinations.serializers import (
    DepartmentResultSerializer,
    DepartmentSerializer,
    DepartmentTemplateSerializer,
    ExaminationSerializer,
    ExamPackageSerializer,
    ExportJobSerializer,
    ImportJobSerializer,
)


@extend_schema_view(
    list=extend_schema(summary="List departments"),
    retrieve=extend_schema(summary="Department detail"),
    create=extend_schema(summary="Create department (admin)"),
    update=extend_schema(summary="Update department (admin)"),
    partial_update=extend_schema(summary="Partially update department (admin)"),
    destroy=extend_schema(summary="Deactivate department (admin)"),
)
class DepartmentViewSet(viewsets.ModelViewSet):
    """CRUD for medical departments. Admin writes; clinical staff read-only.

    Query params:
        parent: filter by parent ID (null for roots)
        tree:    return nested tree (overrides list)
    """

    serializer_class = DepartmentSerializer
    permission_classes = [DepartmentPermission]
    filterset_fields = ["is_active", "category", "parent"]
    search_fields = ["name", "code"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self) -> QuerySet[Department]:
        qs = Department.objects.select_related("parent").prefetch_related("children")
        parent = self.request.query_params.get("parent")
        if parent is not None:
            if parent.lower() == "null":
                qs = qs.filter(parent__isnull=True)
            else:
                qs = qs.filter(parent_id=parent)
        return qs

    def perform_destroy(self, instance: Department) -> None:
        """Soft delete: deactivate instead of removing (packages depend on it)."""
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

    @extend_schema(
        summary="Get department tree",
        description="Returns all active departments as a nested tree structure.",
        responses={200: OpenApiResponse(response=list)},
    )
    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request: Request) -> Response:
        tree_data = Department.build_tree()
        return Response(tree_data)


@extend_schema_view(
    list=extend_schema(summary="List department templates (filter by department)"),
    retrieve=extend_schema(summary="Template detail"),
    create=extend_schema(summary="Create template"),
    update=extend_schema(summary="Update template (increments version)"),
    partial_update=extend_schema(summary="Partially update template"),
    destroy=extend_schema(summary="Deactivate template"),
)
class DepartmentTemplateViewSet(viewsets.ModelViewSet):
    """CRUD for department tabular form definitions. Admin/Doctor write."""

    serializer_class = DepartmentTemplateSerializer
    permission_classes = [TemplatePackagePermission]
    filterset_fields = ["department", "is_active"]
    search_fields = ["name"]
    ordering_fields = ["name", "version", "created_at"]
    ordering = ["department__name", "name"]

    def get_queryset(self) -> QuerySet[DepartmentTemplate]:
        return DepartmentTemplate.objects.select_related("department")

    def perform_destroy(self, instance: DepartmentTemplate) -> None:
        """Soft delete: deactivate; packages may still reference this version."""
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

    @extend_schema(
        summary="Render form schema",
        description="Returns the fields_config array for frontend rendering.",
    )
    @action(detail=True, methods=["get"])
    def render(self, request: Request, pk: str | None = None) -> Response:
        template = self.get_object()
        return Response(
            {
                "id": str(template.id),
                "department": str(template.department_id),
                "name": template.name,
                "version": template.version,
                "fields_config": template.fields_config,
            }
        )

    @extend_schema(
        summary="Download Excel template for this department template",
        description=(
            "Generates a blank .xlsx file with employee_code and all field keys "
            "from fields_config. Row 2 includes Vietnamese labels; row 3 units; "
            "row 4 normal ranges."
        ),
        responses={200: OpenApiResponse(description="Excel .xlsx file")},
    )
    @action(detail=True, methods=["get"], url_path="export-template")
    def export_template(self, request: Request, pk: str | None = None) -> HttpResponse:
        template = self.get_object()
        content = generate_department_template(
            department_name=template.department.name,
            fields_config=template.fields_config,
        )
        safe_name = template.department.code or "department"
        filename = f"Mau_{safe_name}.xlsx"
        response = HttpResponse(
            content,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


@extend_schema_view(
    retrieve=extend_schema(summary="Import job status"),
)
class ImportJobViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only endpoint for checking Excel import job status."""

    serializer_class = ImportJobSerializer
    permission_classes = [ImportPermission]

    def get_queryset(self) -> QuerySet[ImportJob]:
        if getattr(self, "swagger_fake_view", False):
            return ImportJob.objects.none()

        user = self.request.user
        queryset = ImportJob.objects.select_related("department", "created_by")

        if user.role == ROLE_ADMIN:
            return queryset
        return queryset.filter(created_by=user)


class DepartmentImportViewSet(viewsets.ViewSet):
    """Per-department Excel import endpoint."""

    permission_classes = [ImportPermission]
    parser_classes = [MultiPartParser]

    def _get_department(self, department_id: str) -> Department:
        return get_object_or_404(Department, pk=department_id, is_active=True)

    def _get_exam_package(self, exam_package_id: str) -> ExamPackage:
        try:
            return ExamPackage.objects.get(pk=exam_package_id, is_active=True)
        except ExamPackage.DoesNotExist:
            raise ValidationError(
                {"exam_package_id": "Không tìm thấy gói khám với ID đã chọn."}
            )

    def _get_company_exam_package(
        self, company_id: str, exam_package_id: str
    ) -> CompanyExamPackage:
        from accounts.models import CompanyExamPackage

        cep, _ = CompanyExamPackage.objects.get_or_create(
            company_id=company_id,
            exam_package_id=exam_package_id,
            defaults={
                "pricing_mode": "package_total",
                "total_employees": 0,
            },
        )
        return cep

    def _guard_import_permission(
        self, request: Request, department: Department
    ) -> None:
        role = request.user.role
        if role not in {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LABTECH}:
            raise PermissionDenied("Bạn không có quyền import dữ liệu khám.")
        if not can_edit_department(role, department):
            raise PermissionDenied("Bạn không có quyền import dữ liệu của khoa này.")

    def _spawn_department_results(self, examination: Examination) -> None:
        """Create one DepartmentResult per department in the package (if missing),
        and seed field values with ``default_value`` (gender-aware) from the template."""
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
        if to_create:
            results = DepartmentResult.objects.bulk_create(to_create)
            # Seed default values from template fields.
            values_to_create = []
            for result_obj in results:
                binding = next(
                    b
                    for b in bindings
                    if b.template_id == result_obj.template_id
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

    def _process_rows_sync(
        self,
        job: ImportJob,
        department: Department,
        exam_date: date,
        rows: list[dict],
        fields_config: list[dict],
        company_id: str | None = None,
        exam_package_id: str | None = None,
    ) -> None:
        """Process import rows synchronously for small files (<=100 rows)."""
        from patients.models import Patient

        total_rows = len(rows)
        success_count = 0
        updated_count = 0
        skipped_count = 0
        errors: list[dict] = []

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

            # Find existing examination for this patient + package
            examination = Examination.objects.filter(
                patient=patient,
                exam_package_id=exam_package_id,
            ).first()

            if examination is None:
                # Create new examination with the selected package
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

                company_exam_package = self._get_company_exam_package(
                    company_id or patient.company_id,
                    exam_package_id,
                )
                exam_package = self._get_exam_package(exam_package_id)

                examination = Examination.objects.create(
                    patient=patient,
                    company_exam_package=company_exam_package,
                    exam_package=exam_package,
                    exam_type=exam_package.exam_type,
                    exam_date=exam_date,
                    status=Examination.STATUS_COMPLETED,
                    doctor=user,
                )
                # Spawn all DepartmentResults from the package
                self._spawn_department_results(examination)
            else:
                # Ensure department results exist for the package
                self._spawn_department_results(examination)
                # Update to completed if not already
                if (
                    examination.status != Examination.STATUS_COMPLETED
                    or user.role == ROLE_ADMIN
                ):
                    examination.status = Examination.STATUS_COMPLETED
                    examination.doctor = user
                    examination.save(
                        update_fields=["status", "doctor", "version", "updated_at"]
                    )

            # Update the import target department's result
            result = DepartmentResult.objects.filter(
                examination=examination,
                department=department,
            ).first()
            if result is None:
                result = DepartmentResult.objects.create(
                    examination=examination,
                    department=department,
                    template_snapshot=fields_config,
                )
                success_count += 1
            else:
                updated_count += 1

            imported_data = {
                key: value
                for key, value in row.items()
                if key not in {"employee_code", "_row"}
            }
            result.apply_imported_values(imported_data, fields_config)
            result.completed_by = user
            result.completed_at = timezone.now()
            result.save(
                update_fields=[
                    "completed_by",
                    "completed_at",
                    "version",
                    "updated_at",
                ]
            )

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

    @extend_schema(
        summary="Import Excel file for one department",
        description=(
            "Uploads an .xlsx file with company_id + exam_package_id. "
            "Matches patients by employee_code + company, creates/finds "
            "Examination (status=confirmed, doctor=current_user) using the "
            "chosen package, and updates only the selected department's "
            "DepartmentResult data."
        ),
    )
    def create(self, request: Request, department_id: str | None = None) -> Response:
        if not department_id:
            raise ValidationError({"department_id": "Thiếu department_id."})

        department = self._get_department(department_id)
        self._guard_import_permission(request, department)

        company_id = request.data.get("company_id")
        if not company_id:
            raise ValidationError({"company_id": "Vui lòng chọn công ty."})

        exam_package_id = request.data.get("exam_package_id")
        if not exam_package_id:
            raise ValidationError({"exam_package_id": "Vui lòng chọn gói khám."})

        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            raise ValidationError({"file": "Vui lòng upload file Excel."})

        exam_date_str = (
            request.data.get("exam_date") or timezone.localdate().isoformat()
        )
        try:
            exam_date = date.fromisoformat(str(exam_date_str))
        except ValueError as exc:
            raise ValidationError(
                {"exam_date": "Định dạng ngày phải là YYYY-MM-DD."}
            ) from exc

        template = (
            DepartmentTemplate.objects.filter(
                department=department,
                is_active=True,
            )
            .order_by("-version")
            .first()
        )
        if template is None:
            raise ValidationError(
                {"department": "Khoa này chưa có template active để import."}
            )

        file_bytes = uploaded_file.read()
        try:
            _headers, rows = parse_department_import(file_bytes, template.fields_config)
        except ValueError as exc:
            raise ValidationError({"file": str(exc)}) from exc

        # Persist file for audit/status and async processing if needed.
        job = ImportJob.objects.create(
            department=department,
            exam_date=exam_date,
            file=uploaded_file,
            status=ImportJob.STATUS_PENDING,
            created_by=request.user,
        )

        if len(rows) > 100:
            from examinations.tasks import process_excel_import

            process_excel_import.delay(
                str(job.id),
                str(department.id),
                exam_date.isoformat(),
                job.file.path,
                company_id=company_id,
                exam_package_id=exam_package_id,
            )
            return Response(
                ImportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED
            )

        job.status = ImportJob.STATUS_PROCESSING
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at", "updated_at"])
        self._process_rows_sync(
            job,
            department,
            exam_date,
            rows,
            template.fields_config,
            company_id=company_id,
            exam_package_id=exam_package_id,
        )
        job.refresh_from_db()
        return Response(ImportJobSerializer(job).data, status=status.HTTP_201_CREATED)


class ExportJobViewSet(viewsets.GenericViewSet):
    """
    Excel export endpoints:
    - POST /api/export/ — trigger async export
    - GET /api/export/{id}/ — poll status
    - GET /api/export/{id}/download/ — download file
    """

    serializer_class = ExportJobSerializer
    permission_classes = [ImportPermission]  # Same roles: Admin/Doctor/Nurse/LabTech

    def get_queryset(self) -> QuerySet[ExportJob]:
        if getattr(self, "swagger_fake_view", False):
            return ExportJob.objects.none()

        user = self.request.user
        queryset = ExportJob.objects.select_related(
            "company", "department", "exam_package", "created_by"
        )
        if user.role == ROLE_ADMIN:
            return queryset
        return queryset.filter(created_by=user)

    @extend_schema(
        summary="Trigger async Excel export",
        description=(
            "Creates an export job for a company's employees with pre-populated "
            "exam results for one department of the company's active package. "
            "exam_date is ignored — results are taken from the selected package."
        ),
    )
    def create(self, request: Request) -> Response:
        company_id = request.data.get("company_id")
        exam_package_id = request.data.get("package_id") or request.data.get(
            "exam_package_id"
        )
        department_id = request.data.get("department_id")
        mode = request.data.get("mode", "all")

        if not company_id:
            raise ValidationError({"company_id": "Vui lòng chọn công ty."})
        if not exam_package_id:
            raise ValidationError(
                {"package_id": "Vui lòng chọn gói khám."}
            )
        if not department_id:
            raise ValidationError({"department_id": "Vui lòng chọn khoa."})
        if mode not in {"all", "pending"}:
            raise ValidationError(
                {"mode": "Chế độ không hợp lệ. Chọn 'all' hoặc 'pending'."}
            )

        from accounts.models import Company, CompanyExamPackage

        get_object_or_404(Company, pk=company_id, is_active=True)
        get_object_or_404(ExamPackage, pk=exam_package_id, is_active=True)
        department = get_object_or_404(Department, pk=department_id, is_active=True)
        if not CompanyExamPackage.objects.filter(
            company_id=company_id,
            exam_package_id=exam_package_id,
            is_active=True,
        ).exists():
            raise ValidationError(
                {
                    "package_id": (
                        "Công ty không có gói khám đang active tương ứng."
                    )
                }
            )

        role = request.user.role
        if not can_edit_department(role, department):
            raise PermissionDenied("Bạn không có quyền export dữ liệu của khoa này.")

        export_job = ExportJob.objects.create(
            company_id=company_id,
            exam_package_id=exam_package_id,
            department_id=department_id,
            exam_date=None,
            status=ExportJob.STATUS_PENDING,
            created_by=request.user,
        )

        # Check if small dataset — complete synchronously
        from patients.models import Patient

        patient_count = Patient.objects.filter(
            company_id=company_id, is_active=True
        ).count()

        if patient_count <= 50:
            # Process synchronously
            from examinations.tasks import process_excel_export

            process_excel_export(
                str(export_job.id),
                str(company_id),
                str(exam_package_id),
                str(department_id),
                exam_date_str=None,
                mode=mode,
            )
            export_job.refresh_from_db()
            return Response(
                ExportJobSerializer(export_job).data,
                status=status.HTTP_201_CREATED,
            )
        else:
            # Async via Celery
            from examinations.tasks import process_excel_export

            process_excel_export.delay(
                str(export_job.id),
                str(company_id),
                str(exam_package_id),
                str(department_id),
                exam_date_str=None,
                mode=mode,
            )
            return Response(
                ExportJobSerializer(export_job).data,
                status=status.HTTP_202_ACCEPTED,
            )

    @extend_schema(
        summary="Poll export job status",
        responses={200: ExportJobSerializer},
    )
    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        export_job = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(ExportJobSerializer(export_job).data)

    @extend_schema(
        summary="Download exported Excel file",
        responses={200: OpenApiResponse(description="Excel .xlsx file")},
    )
    @action(detail=True, methods=["get"])
    def download(self, request: Request, pk: str | None = None) -> HttpResponse:
        export_job = get_object_or_404(self.get_queryset(), pk=pk)
        if export_job.status != ExportJob.STATUS_COMPLETED:
            raise ValidationError(
                {"status": "File chưa sẵn sàng. Vui lòng đợi export hoàn tất."}
            )
        if not export_job.file:
            raise ValidationError({"file": "Không tìm thấy file export."})

        file_content = export_job.file.read()
        filename = export_job.file.name.split("/")[-1]
        response = HttpResponse(
            file_content,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @extend_schema(
        summary="List export jobs",
    )
    def list(self, request: Request) -> Response:
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ExportJobSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ExportJobSerializer(queryset, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List exam packages",
        parameters=[
            OpenApiParameter("exam_type", str, description="Filter by exam type"),
        ],
    ),
    retrieve=extend_schema(summary="Exam package detail with departments"),
    create=extend_schema(summary="Create exam package (nested departments)"),
    update=extend_schema(summary="Update exam package"),
    partial_update=extend_schema(summary="Partially update exam package"),
    destroy=extend_schema(summary="Deactivate exam package"),
)
class ExamPackageViewSet(viewsets.ModelViewSet):
    """CRUD for exam packages (gói khám). Admin/Doctor write."""

    serializer_class = ExamPackageSerializer
    permission_classes = [TemplatePackagePermission]
    filterset_fields = ["exam_type", "is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self) -> QuerySet[ExamPackage]:
        return ExamPackage.objects.prefetch_related(
            "package_departments__department",
            "package_departments__template",
        )

    def perform_destroy(self, instance: ExamPackage) -> None:
        """Soft delete: deactivate the package instead of removing it."""
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


@extend_schema_view(
    list=extend_schema(
        summary="List examinations",
        parameters=[
            OpenApiParameter("patient", str, description="Filter by patient id"),
            OpenApiParameter("exam_type", str, description="Filter by exam type"),
            OpenApiParameter("status", str, description="Filter by status"),
            OpenApiParameter(
                "company", str, description="Filter by patient company id"
            ),
            OpenApiParameter("date_from", str, description="exam_date >= (YYYY-MM-DD)"),
            OpenApiParameter("date_to", str, description="exam_date <= (YYYY-MM-DD)"),
        ],
    ),
    retrieve=extend_schema(summary="Examination detail with nested department results"),
    create=extend_schema(
        summary="Create examination (auto-spawns department results from package)"
    ),
    update=extend_schema(summary="Update exam-level fields (conclusion, exam_date...)"),
    partial_update=extend_schema(summary="Partially update exam-level fields"),
    destroy=extend_schema(summary="Delete examination (only if draft)"),
)
class ExaminationViewSet(viewsets.ModelViewSet):
    """
    CRUD for examinations plus per-department result entry.

    - Creating an exam spawns one DepartmentResult per package department.
    - Department data is saved/marked-done via nested routes; writes are locked
      to the user's editable department category (Nurse=clinical,
      LabTech=para_clinical, Doctor/Admin=all).
    """

    serializer_class = ExaminationSerializer
    permission_classes = [ExaminationEntryPermission]
    filterset_fields = ["patient", "exam_type", "status"]
    ordering_fields = ["exam_date", "created_at"]
    ordering = ["-exam_date"]

    def get_queryset(self) -> QuerySet[Examination]:
        if getattr(self, "swagger_fake_view", False):
            return Examination.objects.none()

        queryset = (
            Examination.objects.select_related("patient", "patient__company", "doctor")
            .prefetch_related("department_results__department")
            .all()
        )

        # Role-based scoping mirrors the patient queryset rules.
        user = self.request.user
        if user.role == ROLE_COMPANY_ADMIN:
            queryset = queryset.filter(patient__company_id=user.company_id)
        elif user.role == ROLE_LABTECH:
            assigned = user.staff_assignments.values_list("company_id", flat=True)
            queryset = queryset.filter(
                Q(patient__company_id__in=list(assigned))
                | Q(patient__company_id__isnull=True)
            )

        params = self.request.query_params
        company = params.get("company")
        if company:
            queryset = queryset.filter(patient__company_id=company)
        date_from = params.get("date_from")
        if date_from:
            queryset = queryset.filter(exam_date__gte=date_from)
        date_to = params.get("date_to")
        if date_to:
            queryset = queryset.filter(exam_date__lte=date_to)
        return queryset

    def perform_destroy(self, instance: Examination) -> None:
        if instance.status != Examination.STATUS_DRAFT:
            raise ValidationError("Chỉ có thể xóa phiếu khám ở trạng thái nháp.")
        instance.delete()

    # -- Status workflow ---------------------------------------------------

    @extend_schema(
        summary="Change examination status (workflow)",
        description=(
            "Manual transitions: completed → confirmed (doctor/admin) or "
            "confirmed → completed (admin reopen). "
            "draft → completed is automatic when all department fields are filled."
        ),
        request={
            "application/json": {
                "type": "object",
                "properties": {"status": {"type": "string"}},
            }
        },
        responses={200: ExaminationSerializer},
    )
    @action(detail=True, methods=["patch"])
    def status(self, request: Request, pk: str | None = None) -> Response:
        examination = self.get_object()
        target = request.data.get("status")
        if target not in dict(Examination.STATUS_CHOICES):
            raise ValidationError({"status": "Trạng thái không hợp lệ."})
        if target == Examination.STATUS_DRAFT:
            raise ValidationError(
                {"status": "Trạng thái 'draft' được tính tự động khi dữ liệu chưa đủ."}
            )
        if target == Examination.STATUS_COMPLETED and examination.status != Examination.STATUS_CONFIRMED:
            raise ValidationError(
                {
                    "status": (
                        "Trạng thái 'completed' được tính tự động khi tất cả "
                        "khoa đã có đủ dữ liệu."
                    )
                }
            )
        try:
            workflow.transition(examination, target, request.user.role)
        except workflow.WorkflowError as exc:
            raise ValidationError({"status": str(exc)}) from exc
        serializer = self.get_serializer(examination)
        return Response(serializer.data)

    # -- Form rendering ----------------------------------------------------

    def _sync_department_results(self, examination: Examination) -> None:
        """Spawn missing DepartmentResults for departments added to the
        package after the exam was created."""
        package = examination.exam_package
        if package is None:
            return
        bindings = package.package_departments.select_related(
            "department", "template"
        ).all()
        existing = set(
            DepartmentResult.objects.filter(examination=examination).values_list(
                "department_id", "template_id"
            )
        )
        to_create: list[DepartmentResult] = []
        for binding in bindings:
            if (binding.department_id, binding.template_id) in existing:
                continue
            fields = binding.template.fields_config
            initial_data: dict = {}
            for field in fields:
                if field.get("default_value") is not None:
                    initial_data[field["key"]] = field["default_value"]
            result = DepartmentResult(
                examination=examination,
                department=binding.department,
                template=binding.template,
                template_snapshot=fields,
            )
            to_create.append(result)
        if to_create:
            created = DepartmentResult.objects.bulk_create(to_create)
            for result in created:
                defaults: dict = {}
                for field in result.template_snapshot or []:
                    if field.get("default_value") is not None:
                        defaults[field["key"]] = field["default_value"]
                if defaults:
                    result._sync_values(defaults)

    @extend_schema(
        summary="Get all departments + template snapshots + data for form",
        responses={200: OpenApiResponse(description="Form schema + existing data")},
    )
    @action(detail=True, methods=["get"])
    def form(self, request: Request, pk: str | None = None) -> Response:
        examination = self.get_object()
        role = request.user.role

        # Auto-sync: spawn missing DepartmentResults for departments added
        # to the package after the exam was created
        self._sync_department_results(examination)

        results = examination.department_results.select_related("department").all()
        departments = []
        for result in results:
            fields_table = []
            for col in result.template_snapshot:
                fields_table.append({**col, "value": result.data.get(col.get("key"))})
            departments.append(
                {
                    "result_id": str(result.id),
                    "template_id": (
                        str(result.template_id) if result.template_id else None
                    ),
                    "department": {
                        "id": str(result.department_id),
                        "name": result.department.name,
                        "code": result.department.code,
                        "category": result.department.category,
                    },
                    "editable": can_edit_department(role, result.department),
                    "template_snapshot": result.template_snapshot,
                    "data": result.data,
                    "fields_table": fields_table,
                    "completed_at": result.completed_at,
                    "completed": result.completed_at is not None,
                    "version": result.version,
                }
            )
        return Response(
            {
                "id": str(examination.id),
                "status": examination.status,
                "exam_type": examination.exam_type,
                "consultation": examination.consultation,
                "conclusion": examination.conclusion,
                "work_fitness": examination.work_fitness,
                "patient_gender": examination.patient.gender if examination.patient_id else None,
                "departments": departments,
            }
        )

    # -- Department result entry ------------------------------------------

    def _get_department_result(
        self, examination: Examination, dept_id: str
    ) -> DepartmentResult:
        # Try primary key lookup first (supports duplicate departments —
        # frontend passes DepartmentResult.id as dept_id).
        try:
            result = DepartmentResult.objects.select_related(
                "department", "examination"
            ).get(examination=examination, id=dept_id)
            return result
        except DepartmentResult.DoesNotExist:
            pass

        # Fallback: lookup by department_id (backward compatibility).
        result = (
            DepartmentResult.objects.filter(
                examination=examination,
                department_id=dept_id,
            )
            .select_related("department", "examination")
            .first()
        )

        if result is not None:
            return result

        # Auto-create missing DepartmentResult (e.g. department added to package
        # after exam was created). Snapshot the template from the exam's package.
        department = get_object_or_404(Department, pk=dept_id, is_active=True)
        template_snapshot: list = []
        if examination.exam_package:
            binding = (
                examination.exam_package.package_departments.filter(
                    department_id=dept_id
                )
                .select_related("template")
                .first()
            )
            if binding:
                template_snapshot = binding.template.fields_config or []

        result = DepartmentResult.objects.create(
            examination=examination,
            department=department,
            template_snapshot=template_snapshot,
        )

        # Seed data with default_value from field definitions
        defaults: dict = {}
        for field in template_snapshot:
            if field.get("default_value") is not None:
                defaults[field["key"]] = field["default_value"]
        if defaults:
            result._sync_values(defaults)

        return result

    def _guard_department_write(self, result: DepartmentResult) -> None:
        role = self.request.user.role
        if (
            result.examination.status == Examination.STATUS_CONFIRMED
            and role != ROLE_ADMIN
        ):
            raise PermissionDenied("Phiếu khám đã xác nhận không thể chỉnh sửa.")
        if not can_edit_department(role, result.department):
            raise PermissionDenied("Bạn không có quyền chỉnh sửa dữ liệu của khoa này.")

    @extend_schema(
        summary="Save data for one department",
        request=DepartmentResultSerializer,
        responses={200: DepartmentResultSerializer},
    )
    @action(
        detail=True,
        methods=["put"],
        url_path="departments/(?P<dept_id>[^/.]+)",
    )
    def department(
        self, request: Request, pk: str | None = None, dept_id: str | None = None
    ) -> Response:
        examination = self.get_object()
        # Ensure all package bindings have DepartmentResults (handles
        # templates added after exam creation).
        if examination.exam_package:
            serializer = self.get_serializer()
            serializer._spawn_department_results(examination)
        result = self._get_department_result(examination, dept_id)
        self._guard_department_write(result)

        # Accept either flat dict or table-format array of {key, value}.
        data = request.data.get("data")
        fields_table = request.data.get("fields_table")
        if isinstance(fields_table, list):
            data = {
                row["key"]: row.get("value") for row in fields_table if "key" in row
            }
        if not isinstance(data, dict):
            raise ValidationError(
                {
                    "data": (
                        "Gửi 'data' (object) hoặc 'fields_table' (mảng "
                        "[{key, value}])."
                    )
                }
            )
        fields_for_formula = (
            result.template.fields_config
            if result.template
            else result.template_snapshot
        )
        gender = examination.patient.gender if examination.patient_id else None
        data = evaluate_computed_fields(fields_for_formula, data, gender=gender)
        # User save must persist submitted values only — do not invent random
        # lab numbers for keys the client omitted (empty payload used to look
        # like a successful save).
        result._sync_values(data, randomize=False)
        result.save(update_fields=["version", "updated_at"])
        return Response(DepartmentResultSerializer(result).data)

    @extend_schema(
        summary="Mark a department result as completed",
        responses={200: DepartmentResultSerializer},
    )
    @action(
        detail=True,
        methods=["patch"],
        url_path="departments/(?P<dept_id>[^/.]+)/complete",
    )
    def department_complete(
        self, request: Request, pk: str | None = None, dept_id: str | None = None
    ) -> Response:
        examination = self.get_object()
        result = self._get_department_result(examination, dept_id)
        self._guard_department_write(result)
        result.completed_by = request.user
        result.completed_at = timezone.now()
        result.save(
            update_fields=["completed_by", "completed_at", "version", "updated_at"]
        )
        return Response(DepartmentResultSerializer(result).data)

    @extend_schema(
        summary="Get aggregated findings text from all department results",
        responses={
            200: OpenApiResponse(
                response={"type": "object", "properties": {"findings": {"type": "string"}}},
                description="Concatenated findings from all department results",
            )
        },
    )
    @action(detail=True, methods=["get"])
    def findings(self, request: Request, pk: str | None = None) -> Response:
        examination = self.get_object()
        findings_text = aggregate_findings(examination)
        return Response({"findings": findings_text})

    @extend_schema(
        summary="Diagnosis — match findings to known keywords",
        description="Runs aggregate_findings() then matches each finding part "
        "against DiagnosisKeyword records. Returns matched diseases with "
        "conclusion templates.",
        responses={
            200: OpenApiResponse(
                response={"type": "array", "items": {"type": "object"}},
                description="List of matched diagnoses",
            )
        },
    )
    @action(detail=True, methods=["get"], url_path="diagnosis")
    def diagnosis(self, request: Request, pk: str | None = None) -> Response:
        examination = self.get_object()
        findings_text = aggregate_findings(examination, skip_known_keywords=False)
        results = match_diagnosis(findings_text)

        # Summary classification: worst wins (5 > 4 > 3 > 2 > 1).
        classifications = {r["classification"] for r in results}
        classification = None
        for level in (5, 4, 3, 2, 1):
            if level in classifications:
                classification = level
                break

        return Response({"matches": results, "classification": classification})
