from __future__ import annotations

from datetime import datetime, date
from io import BytesIO

from django.db import transaction
from django.db.models import (
    Case,
    Count,
    F,
    FloatField,
    Func,
    IntegerField,
    Q,
    QuerySet,
    Sum,
    Value,
    When,
)
from django.db.models.fields.json import JSONField as JSONBField
from django.db.models.functions import Cast
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from openpyxl import Workbook
from openpyxl.styles import Font
from rest_framework import status, viewsets
from rest_framework.decorators import action, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.models import Company, CompanyExamPackage
from core.permissions import (
    ROLE_ADMIN,
    ROLE_COMPANY_ADMIN,
    ROLE_LABTECH,
)
from patients.filters import PatientFilter
from patients.models import Patient
from patients.permissions import CompanyPermission, PatientPermission
from patients.serializers import (
    CompanyExamPackageSerializer,
    CompanySerializer,
    PatientDetailSerializer,
    PatientSerializer,
)


@extend_schema_view(
    list=extend_schema(summary="List companies"),
    retrieve=extend_schema(summary="Company detail"),
    create=extend_schema(summary="Create company"),
    update=extend_schema(summary="Update company"),
    partial_update=extend_schema(summary="Partially update company"),
    destroy=extend_schema(summary="Soft-delete company"),
)
class CompanyViewSet(viewsets.ModelViewSet):
    """CRUD for the company registry. Admin writes; doctor read-only."""

    serializer_class = CompanySerializer
    permission_classes = [CompanyPermission]
    filterset_fields = ["is_active"]
    search_fields = ["name", "code", "tax_code", "contact_person"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self) -> QuerySet[Company]:
        return Company.objects.annotate(
            patient_count_annotated=Count(
                "patients", filter=Q(patients__is_active=True)
            )
        )

    def perform_destroy(self, instance: Company) -> None:
        """Soft delete: deactivate the company instead of removing it."""
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


@extend_schema_view(
    list=extend_schema(summary="List patients (search + filter + paginate)"),
    retrieve=extend_schema(summary="Patient detail with examination timeline"),
    create=extend_schema(summary="Create patient"),
    update=extend_schema(summary="Update patient"),
    partial_update=extend_schema(summary="Partially update patient"),
    destroy=extend_schema(summary="Soft-delete patient"),
)
class PatientViewSet(viewsets.ModelViewSet):
    """
    CRUD for patients with search, filtering, pagination and role scoping.

    - Admin: full CRUD, sees active and inactive records.
    - Doctor / Nurse: read active patients incl. cá nhân (view_all).
    - LabTech: read active patients in assigned companies + cá nhân (view_assigned).
    - CompanyAdmin: read active patients of their own company only
      (view_own_company; cá nhân patients are NOT visible).
    """

    permission_classes = [PatientPermission]
    filterset_class = PatientFilter
    search_fields = [
        "full_name",
        "employee_code",
        "cccd",
        "phone",
        "company__code",
    ]
    ordering_fields = ["full_name",
                       "employee_code", "start_date", "created_at",
                       "exam_status", "exam_done", "exam_filled",
                       "exam_progress"]
    ordering = ["full_name"]

    def get_serializer_class(self):  # type: ignore[override]
        if self.action == "retrieve":
            return PatientDetailSerializer
        return PatientSerializer

    def list(self, request: Request, *args, **kwargs):
        if request.query_params.get("examination") == "1":
            self.ordering_fields = [
                "full_name", "employee_code", "start_date", "created_at",
                "exam_status", "exam_done",
            ]
        return super().list(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[Patient]:
        # drf-spectacular introspects with an AnonymousUser; short-circuit.
        if getattr(self, "swagger_fake_view", False):
            return Patient.objects.none()

        user = self.request.user
        queryset = Patient.objects.select_related("company")

        # Always annotate latest exam data for sort/filter
        from django.db.models import OuterRef, Subquery
        from examinations.models import DepartmentResult, DepartmentResultValue, Examination

        latest_exam = Examination.objects.filter(
            patient=OuterRef("pk"),
        ).order_by("-exam_date")

        queryset = queryset.annotate(
            _latest_exam_pk=Subquery(latest_exam.values("pk")[:1]),
            exam_status=Subquery(latest_exam.values("status")[:1]),
        )

        done_count = DepartmentResult.objects.filter(
            examination_id=OuterRef("_latest_exam_pk"),
            completed_at__isnull=False,
        ).values("examination_id").annotate(
            cnt=Count("id"),
        ).values("cnt")

        queryset = queryset.annotate(
            exam_done=Subquery(done_count[:1]),
        )

        filled_count = DepartmentResultValue.objects.filter(
            result__examination_id=OuterRef("_latest_exam_pk"),
        ).values("result__examination_id").annotate(
            cnt=Count("id"),
        ).values("cnt")

        queryset = queryset.annotate(
            exam_filled=Subquery(filled_count[:1]),
        )

        # Total field count across all department results of the latest exam.
        # template_snapshot is a JSON array -> use jsonb_array_length.
        total_fields = DepartmentResult.objects.filter(
            examination_id=OuterRef("_latest_exam_pk"),
        ).values("examination_id").annotate(
            total=Sum(
                Func(
                    Cast("template_snapshot", JSONBField()),
                    function="jsonb_array_length",
                    output_field=IntegerField(),
                )
            ),
        ).values("total")

        queryset = queryset.annotate(
            exam_total_fields=Subquery(total_fields[:1]),
        )

        # Progress ratio (0..1) for sorting; NULL-safe.
        queryset = queryset.annotate(
            exam_progress=Case(
                When(
                    exam_total_fields__gt=0,
                    then=Cast("exam_filled", FloatField())
                    / Cast("exam_total_fields", FloatField()),
                ),
                default=Value(0.0),
                output_field=FloatField(),
            )
        )

        # Admin sees everything by default; pass ?active_only=1 to exclude deleted.
        if user.role != ROLE_ADMIN or self.request.query_params.get("active_only") == "1":
            queryset = queryset.filter(is_active=True)

        if user.role == ROLE_COMPANY_ADMIN:
            # Company HR: strictly own company only (no cá nhân patients).
            return queryset.filter(company_id=user.company_id)

        if user.role == ROLE_LABTECH:
            # Assigned companies + cá nhân (no company) patients.
            assigned = user.staff_assignments.values_list(
                "company_id", flat=True)
            return queryset.filter(
                Q(company_id__in=list(assigned)) | Q(company_id__isnull=True)
            )

        # Doctor / Nurse: all active patients (incl. cá nhân).
        return queryset

    def perform_destroy(self, instance: Patient) -> None:
        """Soft delete: set is_active=False; record stays queryable by admin."""
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

    @extend_schema(summary="Download employee import Excel template")
    @action(detail=False, methods=["get"], url_path="import-template")
    def import_template(self, request: Request) -> HttpResponse:
        wb = Workbook()
        ws = wb.active
        ws.title = "Danh sách nhân viên"

        headers = [
            "STT",
            "Bộ phận",
            "Mã NV",
            "Họ và tên",
            "Giới tính",
            "Ngày sinh",
            "Ngày vào",
            "Địa chỉ thường trú",
            "Số CCCD",
            "Ngày cấp",
            "Nơi cấp",
        ]
        header_font = Font(bold=True, size=11)
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font

        sample = [
            "1",
            "Hành chính",
            "NV001",
            "Nguyễn Văn A",
            "Nam",
            "1990-01-01",
            "2024-01-01",
            "123 Đường ABC, Quận 1, TP.HCM",
            "001234567890",
            "2022-06-15",
            "Cục CS QLHC về TTXH",
        ]
        for col_idx, val in enumerate(sample, start=1):
            ws.cell(row=2, column=col_idx, value=val)

        for col_idx in range(1, len(headers) + 1):
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = (
                20
            )

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            'attachment; filename="employee_import_template.xlsx"'
        )
        return response

    @extend_schema(summary="Bulk import employees from Excel")
    @action(
        detail=False,
        methods=["post"],
        parser_classes=[MultiPartParser],
        url_path="import",
    )
    def import_excel(self, request: Request) -> Response:
        company_id = request.data.get("company_id")
        if not company_id:
            return Response(
                {"error": "company_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            company = Company.objects.get(pk=company_id, is_active=True)
        except Company.DoesNotExist:
            return Response(
                {"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND
            )

        file = request.FILES.get("file")
        if not file:
            return Response(
                {"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from openpyxl import load_workbook

            wb = load_workbook(file, read_only=True, data_only=True)
        except Exception as e:
            return Response(
                {"error": f"Cannot read file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sheet = wb.active
        # Skip completely empty rows — some files have formatting extending
        # far beyond the actual data (e.g. max_row = 1,048,576).
        rows = [
            r for r in sheet.iter_rows(min_row=2, values_only=True)
            if any(v is not None and str(v).strip() != "" for v in r)
        ]
        if not rows:
            return Response(
                {
                    "created": 0,
                    "skipped": 0,
                    "examinations_created": 0,
                    "errors": [],
                }
            )

        def _cell_str(row: tuple, idx: int | None) -> str:
            if idx is None or idx >= len(row) or row[idx] is None:
                return ""
            return str(row[idx]).strip()

        def _cell_date(row: tuple, idx: int | None) -> date | None:
            if idx is None or idx >= len(row):
                return None
            val = row[idx]
            if val is None:
                return None
            if isinstance(val, (datetime, date)):
                return val.date() if isinstance(val, datetime) else val
            raw = str(val).strip()
            if not raw:
                return None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(raw, fmt).date()
                except ValueError:
                    continue
            return None

        column_map: dict[str, int | None] = {
            "employee_code": None,
            "department": None,
            "full_name": None,
            "gender": None,
            "dob": None,
            "start_date": None,
            "address": None,
            "cccd": None,
            "cccd_issued_date": None,
            "cccd_issued_place": None,
        }
        header_row = next(sheet.iter_rows(
            min_row=1, max_row=1, values_only=True), None)
        if header_row:
            vi_to_en: dict[str, str] = {
                "stt": "_skip",
                "bộ_phận": "department",
                "mã_nv": "employee_code",
                "họ_và_tên": "full_name",
                "giới_tính": "gender",
                "ngày_sinh": "dob",
                "ngày_vào": "start_date",
                "địa_chỉ_thường_trú": "address",
                "số_cccd": "cccd",
                "ngày_cấp": "cccd_issued_date",
                "nơi_cấp": "cccd_issued_place",
            }
            for idx, col_name in enumerate(header_row):
                key = str(col_name).strip().lower().replace(" ", "_")
                if key in column_map:
                    column_map[key] = idx
                elif key in vi_to_en:
                    en_key = vi_to_en[key]
                    if en_key != "_skip" and en_key in column_map:
                        column_map[en_key] = idx

        created = 0
        skipped = 0
        errors_list: list[dict] = []
        seen_codes: set[str] = set()

        # Preload existing employee codes for this company (single query).
        existing_codes: set[str] = set(
            Patient.objects.filter(
                company=company, employee_code__in=[
                    _cell_str(row, column_map["employee_code"])
                    for row in rows
                ]
            ).values_list("employee_code", flat=True)
        )

        # Pre-scan: collect duplicate employee codes within the same file.
        internal_dupes: set[str] = set()
        codes_in_file: list[str] = []
        for row in rows:
            code = _cell_str(row, column_map["employee_code"])
            codes_in_file.append(code)
            if code and code in seen_codes:
                internal_dupes.add(code)
            seen_codes.add(code)

        to_create: list[Patient] = []

        for row_idx, row in enumerate(rows, start=2):
            try:
                employee_code_val = _cell_str(row, column_map["employee_code"])
                full_name_val = _cell_str(row, column_map["full_name"])
                dept_val = _cell_str(row, column_map["department"])
                gender_raw = _cell_str(row, column_map["gender"]).upper()
                dob_parsed = _cell_date(row, column_map["dob"])
                start_date_val = _cell_date(row, column_map["start_date"])
                address_val = _cell_str(row, column_map["address"])
                cccd_val = _cell_str(row, column_map["cccd"])
                cccd_issued_date_val = _cell_date(
                    row, column_map["cccd_issued_date"])
                cccd_issued_place_val = _cell_str(
                    row, column_map["cccd_issued_place"])

                if not employee_code_val:
                    skipped += 1
                    errors_list.append(
                        {"row": row_idx, "message": "Thiếu mã nhân viên"}
                    )
                    continue
                if not full_name_val:
                    skipped += 1
                    errors_list.append(
                        {"row": row_idx, "message": "Thiếu họ tên"})
                    continue

                if employee_code_val in internal_dupes:
                    skipped += 1
                    errors_list.append(
                        {
                            "row": row_idx,
                            "employee_code": employee_code_val,
                            "message": f"Mã nhân viên {employee_code_val} bị trùng trong file Excel",
                        }
                    )
                    continue

                if employee_code_val in existing_codes:
                    skipped += 1
                    errors_list.append(
                        {
                            "row": row_idx,
                            "employee_code": employee_code_val,
                            "message": f"Mã nhân viên {employee_code_val} đã tồn tại trong công ty",
                        }
                    )
                    continue

                gender_parsed = "M"
                if gender_raw:
                    if gender_raw.upper() in ("F", "FEMALE", "NỮ", "NU"):
                        gender_parsed = "F"

                defaults: dict = {
                    "full_name": full_name_val,
                    "department": dept_val,
                    "gender": gender_parsed,
                    "address": address_val,
                    "cccd": cccd_val,
                    "cccd_issued_place": cccd_issued_place_val,
                    "is_active": True,
                }
                if dob_parsed:
                    defaults["dob"] = dob_parsed
                if start_date_val:
                    defaults["start_date"] = start_date_val
                if cccd_issued_date_val:
                    defaults["cccd_issued_date"] = cccd_issued_date_val

                to_create.append(
                    Patient(
                        company=company,
                        employee_code=employee_code_val,
                        **defaults,
                    )
                )
                created += 1

            except Exception as e:
                skipped += 1
                errors_list.append({"row": row_idx, "message": str(e)})

        examinations_created = 0
        if to_create:
            with transaction.atomic():
                created_patients = Patient.objects.bulk_create(
                    to_create, batch_size=1000
                )
                from examinations.services import (
                    create_seeded_examinations_for_patients,
                )

                examinations_created = create_seeded_examinations_for_patients(
                    created_patients,
                    company=company,
                    doctor=request.user if request.user.is_authenticated else None,
                )

        return Response(
            {
                "created": created,
                "skipped": skipped,
                "examinations_created": examinations_created,
                "errors": errors_list,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(summary="Reactivate a soft-deleted patient (admin only)")
    @action(detail=True, methods=["post"])
    def reactivate(self, request: Request, pk: str | None = None) -> Response:
        if request.user.role != ROLE_ADMIN:
            return Response(
                {"detail": "Chỉ quản trị viên mới có quyền khôi phục bệnh nhân."},
                status=status.HTTP_403_FORBIDDEN,
            )
        patient = self.get_object()
        patient.is_active = True
        patient.save(update_fields=["is_active", "updated_at"])
        return Response(PatientSerializer(patient).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get public report links for employees of a company",
        parameters=[
            OpenApiParameter("company_id", str, required=True),
        ],
    )
    @action(detail=False, methods=["get"], url_path="report-links")
    def report_links(self, request: Request) -> Response:
        company_id = request.query_params.get("company_id")
        if not company_id:
            return Response(
                {"error": "company_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from reports.models import EmployeeExamReport

        reports = EmployeeExamReport.objects.filter(
            examination__patient__company_id=company_id,
            status=EmployeeExamReport.STATUS_DONE,
        ).select_related("examination__patient")

        links = {
            str(r.examination.patient_id): {
                "url": r.public_url,
                "password": r.password,
                "exam_date": r.examination.exam_date.strftime("%d/%m/%Y"),
            }
            for r in reports
        }
        return Response(links, status=status.HTTP_200_OK)

    @extend_schema(summary="Get or create a public report link for one patient")
    @action(detail=True, methods=["get"], url_path="report-link")
    def report_link(self, request: Request, pk: str | None = None) -> Response:
        patient = self.get_object()
        from reports.models import EmployeeExamReport, ReportTemplate
        from reports.tasks import generate_employee_report_task

        # Find the latest examination for this patient.
        exam = (
            patient.examinations.filter(
                company_exam_package__isnull=False,
            )
            .order_by("-exam_date")
            .first()
        )
        if exam is None:
            return Response(
                {"error": "Nhân viên chưa có đợt khám nào."},
                status=status.HTTP_404_NOT_FOUND,
            )

        report, created = EmployeeExamReport.objects.get_or_create(
            examination=exam,
            defaults={
                "template": ReportTemplate.objects.filter(
                    name="Employee Exam Report", is_active=True
                ).first(),
                "status": EmployeeExamReport.STATUS_PROCESSING,
                "created_by": request.user,
            },
        )

        # Generate the report if not done yet.
        if report.status != EmployeeExamReport.STATUS_DONE:
            generate_employee_report_task.delay(str(exam.id))
        elif created:
            generate_employee_report_task.delay(str(exam.id))

        return Response(
            {
                "url": report.public_url,
                "password": report.password,
                "status": report.status,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    list=extend_schema(summary="List exam packages for a company"),
    retrieve=extend_schema(summary="Company exam package detail"),
    create=extend_schema(summary="Assign exam package to company"),
    update=extend_schema(summary="Update company exam package"),
    partial_update=extend_schema(
        summary="Partially update company exam package"),
    destroy=extend_schema(summary="Remove company exam package"),
    price_preview=extend_schema(
        summary="Preview pricing total before saving"),
)
class CompanyExamPackageViewSet(viewsets.ModelViewSet):
    """Sprint 6a — CRUD + price preview for CompanyExamPackage. Admin only."""

    serializer_class = CompanyExamPackageSerializer
    permission_classes = [CompanyPermission]

    def get_queryset(self) -> QuerySet[CompanyExamPackage]:
        company_pk = self.kwargs.get("company_pk")
        return CompanyExamPackage.objects.filter(company_id=company_pk).select_related(
            "exam_package"
        )

    def perform_create(self, serializer: CompanyExamPackageSerializer) -> None:
        company = Company.objects.get(pk=self.kwargs["company_pk"])
        serializer.save(company=company, assigned_by=self.request.user)

    @extend_schema(
        summary="Preview pricing total",
        parameters=[
            {
                "name": "total_employees",
                "in_": "query",
                "required": False,
                "description": "Override total_employees for preview (uses stored value if omitted)",
                "schema": {"type": "integer"},
            }
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "mode": {"type": "string"},
                    "total_employees": {"type": "integer"},
                    "cost_per_employee": {"type": "integer"},
                    "grand_total": {"type": "integer"},
                },
            }
        },
    )
    @action(detail=True, methods=["get"], url_path="price-preview")
    def price_preview(self, request: Request, **kwargs) -> Response:
        obj: CompanyExamPackage = self.get_object()
        total_employees = request.query_params.get("total_employees")
        employees = int(total_employees) if total_employees else obj.total_employees

        cost_per_employee = 0
        if obj.pricing_mode == "package_total":
            cost_per_employee = obj.exam_package.default_package_price or 0
        elif obj.pricing_mode == "per_field":
            for epd in obj.exam_package.package_departments.select_related("template").all():
                for field in epd.template.fields_config:
                    cost_per_employee += field.get("default_price", 0) or 0

        return Response(
            {
                "mode": obj.pricing_mode,
                "total_employees": employees,
                "cost_per_employee": cost_per_employee,
                "grand_total": employees * cost_per_employee,
            }
        )
