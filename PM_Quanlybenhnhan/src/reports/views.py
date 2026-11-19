from __future__ import annotations

import os

from django.db import transaction
from django.http import FileResponse, HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from core.permissions import ROLE_COMPANY_ADMIN
from reports.models import (
    DepartmentReportTemplate,
    Report,
    ReportTemplate,
)
from reports.permissions import ReportPermission, ReportTemplatePermission
from reports.preview import PreviewDataUnavailable, build_preview_dataset
from reports.render import (
    TemplateRenderError,
    build_context,
    build_department_context,
    build_document,
    render_fragment,
    render_report,
)
from reports.serializers import (
    DepartmentReportTemplateSerializer,
    GenerateReportSerializer,
    ReportSerializer,
    ReportTemplateListSerializer,
    ReportTemplateSerializer,
    TemplatePreviewSerializer,
)
from reports.shortcodes import REPORT_VARIABLES


@extend_schema_view(
    list=extend_schema(summary="List generated reports"),
    retrieve=extend_schema(summary="Report detail"),
    create=extend_schema(summary="Generate report (async)"),
    destroy=extend_schema(summary="Delete report"),
    download=extend_schema(summary="Download report file"),
)
class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    permission_classes = [ReportPermission]
    filterset_fields = ["company", "report_type", "status", "output_format"]
    ordering_fields = ["created_at", "report_type", "status"]

    def get_queryset(self):
        qs = Report.objects.select_related("company", "created_by", "template").all()
        user = self.request.user
        # CompanyAdmin only ever sees their own company's reports.
        if getattr(user, "role", None) == ROLE_COMPANY_ADMIN and user.company_id:
            qs = qs.filter(company_id=user.company_id)
        return qs

    def perform_create(self, serializer: ReportSerializer) -> None:
        serializer.save(created_by=self.request.user)

    @extend_schema(
        summary="Generate a new report",
        request=GenerateReportSerializer,
        responses={201: ReportSerializer},
    )
    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request: Request) -> Response:
        return self._generate(request, request.data)

    def _generate(self, request: Request, payload) -> Response:
        input_serializer = GenerateReportSerializer(data=payload)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        template = data.get("template")
        # Only clinical-detail Excel still has a hardcoded legacy builder.
        # HTML always needs a template; company_summary / occupational / cost
        # Excel also need one (the legacy path raises NotImplementedError).
        uses_legacy_excel = (
            data["output_format"] == Report.FORMAT_EXCEL
            and data["report_type"] == Report.REPORT_CLINICAL_DETAIL
        )
        if (
            template is None
            and data.get("use_default_template", True)
            and not uses_legacy_excel
        ):
            template = ReportTemplate.objects.filter(
                report_type=data["report_type"], is_default=True, is_active=True
            ).first()

        if template is None and not uses_legacy_excel:
            if data["output_format"] == Report.FORMAT_HTML:
                error = "Định dạng HTML yêu cầu chọn template_id."
            else:
                label = dict(Report.REPORT_TYPE_CHOICES).get(
                    data["report_type"], data["report_type"]
                )
                error = f"Loại báo cáo '{label}' cần chọn template."
            return Response(
                {"error": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if (
            getattr(user, "role", None) == ROLE_COMPANY_ADMIN
            and user.company_id
            and str(user.company_id) != str(data["company_id"])
        ):
            return Response(
                {"error": "Không có quyền tạo báo cáo cho công ty khác."},
                status=status.HTTP_403_FORBIDDEN,
            )

        report = Report.objects.create(
            company_id=data["company_id"],
            report_type=data["report_type"],
            output_format=data["output_format"],
            template=template,
            parameters={
                "exam_package_id": str(data["exam_package_id"]),
                "exam_date": str(data["exam_date"]) if data.get("exam_date") else None,
            },
            status=Report.STATUS_PROCESSING,
            created_by=user,
        )

        from reports.tasks import generate_report_task

        # ATOMIC_REQUESTS is on: enqueue only after the Report row is visible.
        report_id = str(report.id)
        transaction.on_commit(lambda rid=report_id: generate_report_task.delay(rid))

        return Response(
            ReportSerializer(report, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(summary="Download report file")
    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request: Request, pk: str | None = None) -> Response:
        report = self.get_object()
        if report.status != Report.STATUS_DONE or not report.file:
            return Response(
                {"error": "Báo cáo chưa sẵn sàng để tải."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filename = os.path.basename(report.file.name)
        return FileResponse(
            report.file.open("rb"),
            as_attachment=True,
            filename=filename,
        )

    @extend_schema(
        summary="Generate clinical detail report",
        request=GenerateReportSerializer,
        responses={201: ReportSerializer},
    )
    @action(detail=False, methods=["post"], url_path="clinical-detail")
    def clinical_detail(self, request: Request) -> Response:
        payload = dict(request.data)
        payload["report_type"] = Report.REPORT_CLINICAL_DETAIL
        payload.setdefault("output_format", Report.FORMAT_EXCEL)
        return self._generate(request, payload)


class _PreviewMixin:
    """Shared preview plumbing for both template viewsets."""

    def _preview_response(
        self, request: Request, html: str, output_format: str
    ) -> HttpResponse:
        return HttpResponse(html, content_type="text/html; charset=utf-8")


@extend_schema_view(
    list=extend_schema(summary="List report templates"),
    retrieve=extend_schema(summary="Report template detail"),
    create=extend_schema(summary="Create report template"),
    update=extend_schema(summary="Update report template"),
    destroy=extend_schema(summary="Delete report template"),
)
class ReportTemplateViewSet(_PreviewMixin, viewsets.ModelViewSet):
    queryset = ReportTemplate.objects.prefetch_related(
        "items__department_template", "items__department"
    ).select_related("created_by")
    permission_classes = [ReportTemplatePermission]
    filterset_fields = ["report_type", "body_type", "is_default", "is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "report_type", "created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return ReportTemplateListSerializer
        return ReportTemplateSerializer

    def perform_create(self, serializer: ReportTemplateSerializer) -> None:
        serializer.save(created_by=self.request.user)

    @extend_schema(
        summary="Documented template variables (shortcodes)",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="variables")
    def variables(self, request: Request) -> Response:
        from reports.body_builder import BodyBuilder

        return Response(
            {
                "groups": REPORT_VARIABLES,
                "body_types": [
                    {"value": v, "label": label}
                    for v, label in ReportTemplate.BODY_TYPE_CHOICES
                ],
                "available_body_functions": BodyBuilder.available(),
            }
        )

    @extend_schema(
        summary="Preview a report template (HTML or PDF)",
        request=TemplatePreviewSerializer,
        parameters=[
            OpenApiParameter("company_id", str, description="Dùng dữ liệu thật"),
            OpenApiParameter("exam_package_id", str),
        ],
        responses={200: str},
    )
    @action(detail=True, methods=["post", "get"], url_path="preview")
    def preview(self, request: Request, pk: str | None = None):
        template = self.get_object()
        payload = request.data if request.method == "POST" else request.query_params
        serializer = TemplatePreviewSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        opts = serializer.validated_data

        try:
            dataset = build_preview_dataset(
                company_id=opts.get("company_id"),
                exam_package_id=opts.get("exam_package_id"),
                exam_date=opts.get("exam_date"),
                limit=opts.get("limit", 3),
            )
        except PreviewDataUnavailable as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Apply unsaved overrides from the editor without persisting them.
        if opts.get("body_html") is not None:
            setattr(template, "body_html", opts["body_html"])

        try:
            html = render_report(template, dataset)
        except TemplateRenderError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return self._preview_response(request, html, opts.get("output_format", "html"))


@extend_schema_view(
    list=extend_schema(summary="List department report templates"),
    retrieve=extend_schema(summary="Department report template detail"),
    create=extend_schema(summary="Create department report template"),
    destroy=extend_schema(summary="Delete department report template"),
)
class DepartmentReportTemplateViewSet(_PreviewMixin, viewsets.ModelViewSet):
    queryset = DepartmentReportTemplate.objects.select_related("department")
    serializer_class = DepartmentReportTemplateSerializer
    permission_classes = [ReportTemplatePermission]
    filterset_fields = ["department", "is_active"]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]

    @extend_schema(
        summary="Preview a department template (HTML or PDF)",
        request=TemplatePreviewSerializer,
        responses={200: str},
    )
    @action(detail=True, methods=["post", "get"], url_path="preview")
    def preview(self, request: Request, pk: str | None = None):
        dept_template = self.get_object()
        payload = request.data if request.method == "POST" else request.query_params
        serializer = TemplatePreviewSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        opts = serializer.validated_data

        try:
            dataset = build_preview_dataset(
                company_id=opts.get("company_id"),
                exam_package_id=opts.get("exam_package_id"),
                exam_date=opts.get("exam_date"),
                limit=opts.get("limit", 3),
            )
        except PreviewDataUnavailable as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        body_html = opts.get("body_html")
        if body_html is None:
            body_html = dept_template.body_html

        target_department_id = opts.get("department_id") or dept_template.department_id
        base_context = build_context(dataset)

        blocks: list[str] = []
        try:
            for patient in dataset.patients:
                departments = (
                    patient.departments_for(str(target_department_id))
                    if target_department_id
                    else patient.departments
                )
                if not departments:
                    departments = [None]
                for department in departments:
                    context = build_department_context(
                        patient, department, base_context, dept_template.config or {}
                    )
                    blocks.append(
                        "<section>"
                        + render_fragment(
                            body_html,
                            context,
                            label=f"template khoa '{dept_template.name}'",
                        )
                        + "</section>"
                    )
        except TemplateRenderError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not blocks:
            blocks.append('<p class="empty">Không có dữ liệu khoa phù hợp.</p>')

        html = build_document(
            header=f"<h2>{dept_template.name}</h2>",
            body="".join(blocks),
            footer="",
            page_size=ReportTemplate.PAGE_A4_PORTRAIT,
            title=f"Xem trước — {dept_template.name}",
        )
        return self._preview_response(request, html, opts.get("output_format", "html"))
