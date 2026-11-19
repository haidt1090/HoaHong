"""Diagnosis app views — keyword CRUD, import."""

from __future__ import annotations

from io import BytesIO

from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, extend_schema_view
from openpyxl import Workbook
from openpyxl.styles import Font
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from diagnosis.filters import DiagnosisKeywordFilter
from diagnosis.models import DiagnosisKeyword
from diagnosis.permissions import DiagnosisKeywordPermission
from diagnosis.serializers import (
    DiagnosisKeywordSerializer,
    ImportKeywordsUploadSerializer,
)
from diagnosis.services import import_keywords_from_excel


@extend_schema_view(
    list=extend_schema(summary="List diagnosis keywords"),
    retrieve=extend_schema(summary="Diagnosis keyword detail"),
    create=extend_schema(summary="Create diagnosis keyword (admin)"),
    update=extend_schema(summary="Update diagnosis keyword (admin)"),
    partial_update=extend_schema(summary="Partially update diagnosis keyword (admin)"),
    destroy=extend_schema(summary="Deactivate diagnosis keyword (admin)"),
)
class DiagnosisKeywordViewSet(viewsets.ModelViewSet):
    serializer_class = DiagnosisKeywordSerializer
    permission_classes = [DiagnosisKeywordPermission]
    filterset_class = DiagnosisKeywordFilter
    search_fields = ["keyword", "conclusion_template", "disease_name"]
    ordering_fields = ["keyword", "classification", "created_at"]
    ordering = ["keyword"]

    def get_queryset(self):
        return DiagnosisKeyword.objects.all()

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

    @extend_schema(
        summary="Import keywords from Benh-TuVan 001.xlsx",
        request=ImportKeywordsUploadSerializer,
        responses={200: {"type": "object", "properties": {
            "diseases_created": {"type": "integer"},
            "keywords_created": {"type": "integer"},
        }}},
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="import-keywords",
        parser_classes=[MultiPartParser],
    )
    def import_keywords(self, request: Request) -> Response:
        serializer = ImportKeywordsUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_obj = serializer.validated_data["file"]
        mode = serializer.validated_data.get("mode", "append")

        try:
            result = import_keywords_from_excel(file_obj.read(), mode=mode)
        except Exception as exc:
            raise ValidationError({"file": f"Import failed: {str(exc)}"}) from exc

        return Response(result, status=status.HTTP_200_OK)

    @extend_schema(summary="Download keyword import Excel template")
    @action(detail=False, methods=["get"], url_path="import-template")
    def import_template(self, request: Request) -> HttpResponse:
        wb = Workbook()
        ws = wb.active
        ws.title = "Benh_TuVan"

        headers = [
            "STT", "Nhóm bệnh", "Mã NB", "Mã ICD10", "Tên bệnh",
            "Từ khóa", "Loại khám", "Kết luận",
        ]
        header_font = Font(bold=True, size=11)
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font

        sample = [
            "1", "Bệnh nghề nghiệp", "BNN01", "J60", "Bệnh bụi phổi silic",
            "ho khan, khó thở, đau ngực", "occupational",
            "Có biểu hiện bệnh bụi phổi silic. Đề nghị khám chuyên khoa.",
        ]
        for col_idx, val in enumerate(sample, start=1):
            ws.cell(row=2, column=col_idx, value=val)

        for col_idx in range(1, len(headers) + 1):
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = 22

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="Benh_TuVan_template.xlsx"'
        return response
