"""National sync API views — Phase 8, Sprint 16 (admin only)."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.signatures import (
    clear_signature,
    signature_kind,
    store_signature_base64,
    store_signature_image,
)
from core.permissions import IsAdmin, IsAdminOrDoctor
from examinations.models import Department, DepartmentField, Examination
from nationalsync.mapping import copy_matching_mappings, extract_mapping_fields
from nationalsync.signer_launcher import SIGNER_DOWNLOAD_NAME, build_signer_command
from nationalsync.models import (
    FacilitySignature,
    SyncConfig,
    SyncFieldMapping,
    SyncJob,
    SyncMappingVersion,
)
from nationalsync import xml_builder
from nationalsync.scope import InvalidScope, validate_scope


def _unsigned_xml_cache_key(exam_id: str) -> str:
    return f"nationalsync:unsigned-xml:{exam_id}"
from nationalsync.serializers import (
    SyncConfigSerializer,
    SyncFieldMappingSerializer,
    SyncJobSerializer,
    SyncMappingVersionSerializer,
    SyncScopeSerializer,
)
from nationalsync.tasks import sync_checkup_data

MAX_MAPPING_XML_BYTES = 40 * 1024 * 1024


@extend_schema_view(
    get=extend_schema(summary="Get national sync configs (secrets masked)"),
    put=extend_schema(summary="Update national sync config for an environment (admin)"),
)
class SyncConfigView(APIView):
    permission_classes = [IsAdmin]
    serializer_class = SyncConfigSerializer

    def get(self, request: Request) -> Response:
        data = {}
        for env in (SyncConfig.ENV_SANDBOX, SyncConfig.ENV_PRODUCTION):
            config = SyncConfig.load(env)
            data[env] = self.serializer_class(
                config, context={"request": request}
            ).data
        return Response(data)

    def put(self, request: Request) -> Response:
        environment = request.data.get("environment")
        if environment not in dict(SyncConfig.ENVIRONMENT_CHOICES):
            return Response(
                {"environment": "Chọn môi trường hợp lệ (sandbox / production)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config = SyncConfig.load(environment)
        serializer = self.serializer_class(
            config, data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class SyncValidateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        summary="Validate sync scope — pending, already synced, signature issues",
        request=SyncScopeSerializer,
    )
    def post(self, request: Request) -> Response:
        serializer = SyncScopeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = validate_scope(
                data["scope_type"],
                company_id=data.get("company_id"),
                patient_id=data.get("patient_id"),
                examination_id=data.get("examination_id"),
                environment=data.get("environment") or SyncConfig.ENV_SANDBOX,
            )
        except InvalidScope as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result)


class SyncSigningXmlView(APIView):
    """Unsigned KHAMSUCKHOE XML for each exam the doctor is about to sign."""

    permission_classes = [IsAdmin]

    @extend_schema(summary="XML documents to sign with the doctor's USB token")
    def post(self, request: Request) -> Response:
        serializer = SyncScopeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        examination_id = data.get("examination_id")
        environment = data.get("environment") or SyncConfig.ENV_SANDBOX
        try:
            result = validate_scope(
                data["scope_type"],
                company_id=data.get("company_id"),
                patient_id=data.get("patient_id"),
                examination_id=examination_id,
                environment=environment,
            )
        except InvalidScope as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if result["eligible"] == 0:
            return Response(
                {"detail": "Không có lượt khám nào cần ký."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        config = SyncConfig.load(environment)
        if not config.is_configured:
            return Response(
                {"detail": "Chưa cấu hình đầy đủ SyncConfig cho môi trường đã chọn."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ids = [row["id"] for row in result["eligible_exams"]]
        exams = {
            str(exam.id): exam
            for exam in Examination.objects.filter(pk__in=ids).select_related(
                "patient", "doctor"
            )
        }
        ngay_lap = timezone.localdate()
        payload = []
        for exam_id in ids:
            xml = xml_builder.build_kham_suc_khoe_xml(
                [exams[exam_id]],
                config,
                ngay_lap=ngay_lap,
                facility_signature="",
            )
            cache.set(_unsigned_xml_cache_key(exam_id), xml, timeout=900)
            payload.append({"id": exam_id, "xml": xml})
        return Response({"exams": payload})


class SyncTriggerView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        summary="Trigger a national sync job (admin)",
        request=SyncScopeSerializer,
        responses={201: SyncJobSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = SyncScopeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        examination_id = data.get("examination_id")
        environment = data.get("environment") or SyncConfig.ENV_SANDBOX

        try:
            result = validate_scope(
                data["scope_type"],
                company_id=data.get("company_id"),
                patient_id=data.get("patient_id"),
                examination_id=examination_id,
                environment=environment,
            )
        except InvalidScope as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if result["total"] == 0:
            return Response(
                {"detail": "Không có lượt khám nào trong phạm vi đã chọn."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if result["eligible"] == 0:
            detail = (
                "Lượt khám này đã đồng bộ thành công trước đó."
                if examination_id
                else "Tất cả lượt khám trong phạm vi đã đồng bộ thành công trước đó."
            )
            return Response(
                {
                    "detail": detail,
                    "already_synced": result.get("already_synced", []),
                    "already_synced_count": result.get("already_synced_count", 0),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        config = SyncConfig.load(environment)
        if not config.is_active:
            return Response(
                {"detail": "Đồng bộ đang tắt (is_active=False)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not config.is_configured:
            return Response(
                {"detail": "Chưa cấu hình đầy đủ SyncConfig cho môi trường đã chọn."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        signatures = data.get("cks_nguoi_ket_luan") or {}
        missing = [
            row["id"]
            for row in result["eligible_exams"]
            if row["id"] not in signatures
        ]
        if missing:
            return Response(
                {
                    "detail": (
                        "Thiếu chữ ký USB của cơ sở khám (CKS_BENH_VIEN). "
                        "Cắm USB của cơ sở, chạy chương trình ký, rồi đồng bộ lại."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ngay_lap = timezone.localdate()
        unsigned_xml: dict[str, str] = {}
        for row in result["eligible_exams"]:
            cached = cache.get(_unsigned_xml_cache_key(row["id"]))
            if isinstance(cached, str) and cached:
                unsigned_xml[row["id"]] = cached
                continue
            exam = Examination.objects.select_related("patient", "doctor").get(
                pk=row["id"]
            )
            unsigned_xml[row["id"]] = xml_builder.build_kham_suc_khoe_xml(
                [exam],
                config,
                ngay_lap=ngay_lap,
                facility_signature="",
            )

        job = SyncJob.objects.create(
            environment=config.environment,
            scope_type=data["scope_type"],
            company_id=data.get("company_id"),
            patient_id=data.get("patient_id"),
            examination_id=examination_id,
            examination_count=result["eligible"],
            created_by=request.user,
            cks_nguoi_ket_luan=json.dumps(
                {
                    "signatures": {
                        row["id"]: signatures[row["id"]]
                        for row in result["eligible_exams"]
                    },
                    "xml": unsigned_xml,
                }
            ),
        )
        sync_checkup_data.delay(str(job.id))

        return Response(
            SyncJobSerializer(job, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    list=extend_schema(summary="List national sync jobs (admin)"),
    retrieve=extend_schema(summary="National sync job detail (admin)"),
)
class SyncJobViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = SyncJobSerializer
    queryset = SyncJob.objects.select_related(
        "company", "patient", "examination", "examination__patient", "created_by"
    ).all()
    ordering = ["-created_at"]
    search_fields = ["company__name", "patient__full_name", "created_by__email"]
    filterset_fields = ["status", "scope_type"]


class FacilitySignatureView(APIView):
    """Admin sets the single hospital signature used as ``CKS_BENH_VIEN``."""

    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request: Request) -> Response:
        facility = FacilitySignature.objects.filter(pk=1).first()
        return Response({"signature_kind": signature_kind(facility)})

    def put(self, request: Request) -> Response:
        facility = FacilitySignature.load()
        upload = request.FILES.get("signature_image")
        raw_b64 = request.data.get("signature_base64")
        has_b64 = raw_b64 is not None and str(raw_b64).strip() != ""
        if upload and has_b64:
            return Response(
                {"detail": "Chỉ chọn ảnh PNG hoặc chuỗi base64, không gửi cả hai."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            if upload is not None:
                store_signature_image(facility, upload.read(), filename="facility.png")
            elif has_b64:
                store_signature_base64(facility, str(raw_b64))
            else:
                return Response(
                    {"detail": "Cần file PNG hoặc chuỗi base64."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValidationError as exc:
            message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"signature_kind": signature_kind(facility)})

    def delete(self, request: Request) -> Response:
        facility = FacilitySignature.objects.filter(pk=1).first()
        if facility is not None:
            clear_signature(facility)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SyncMappingVersionViewSet(viewsets.ModelViewSet):
    """Admin uploads a sample XML and chooses which version sync uses."""

    permission_classes = [IsAdmin]
    serializer_class = SyncMappingVersionSerializer
    pagination_class = None
    queryset = SyncMappingVersion.objects.all()
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def create(self, request: Request) -> Response:
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"detail": "Chọn file XML."}, status=status.HTTP_400_BAD_REQUEST
            )
        if upload.size > MAX_MAPPING_XML_BYTES:
            return Response(
                {"detail": "File XML lớn hơn 40MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        raw = upload.read()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        try:
            extracted = extract_mapping_fields(BytesIO(raw))
        except ET.ParseError:
            return Response(
                {"detail": "File XML không đọc được."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        name = str(request.data.get("name") or "").strip()
        if not name:
            name = Path(upload.name or "mapping").stem[:120] or "mapping"
        with transaction.atomic():
            previous = SyncMappingVersion.objects.filter(is_default=True).first()
            version = SyncMappingVersion.objects.create(
                name=name[:120],
                source_filename=(upload.name or "")[:255],
                extracted_fields=extracted,
                is_default=previous is None,
            )
            if previous is not None:
                copy_matching_mappings(previous, version)
        return Response(
            self.get_serializer(version).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(summary="Use this XML version when syncing")
    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request: Request, pk: str | None = None) -> Response:
        del request, pk
        version = self.get_object()
        version.activate()
        return Response(self.get_serializer(version).data)


class SyncFieldMappingViewSet(viewsets.ModelViewSet):
    """Admin maps a department column key to a national XML tag."""

    permission_classes = [IsAdmin]
    serializer_class = SyncFieldMappingSerializer
    pagination_class = None
    queryset = SyncFieldMapping.objects.select_related("department", "version").all()
    http_method_names = ["get", "post", "put", "delete", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        version = self.request.query_params.get("version")
        if version:
            queryset = queryset.filter(version_id=version)
        return queryset

    def get_serializer_context(self) -> dict:
        context = super().get_serializer_context()
        if getattr(self, "swagger_fake_view", False):
            context["field_pairs"] = set()
            return context
        context["field_pairs"] = set(
            DepartmentField.objects.values_list("template__department_id", "key")
        )
        return context

    @extend_schema(summary="XML tags and department column keys for the mapping form")
    @action(detail=False, methods=["get"], url_path="field-options")
    def field_options(self, request: Request) -> Response:
        departments = [
            {"id": str(row.id), "name": row.name, "code": row.code}
            for row in Department.objects.filter(is_active=True).order_by("name")
        ]
        grouped: dict[str, dict[str, dict]] = {}
        rows = DepartmentField.objects.filter(
            template__department__is_active=True
        ).values("key", "label", "template__name", "template__department_id")
        for row in rows:
            dept_id = str(row["template__department_id"])
            bucket = grouped.setdefault(dept_id, {})
            entry = bucket.setdefault(
                row["key"],
                {"key": row["key"], "label": row["label"], "templates": []},
            )
            template_name = row["template__name"]
            if template_name not in entry["templates"]:
                entry["templates"].append(template_name)
        fields = {
            dept_id: sorted(items.values(), key=lambda item: item["label"])
            for dept_id, items in grouped.items()
        }
        version_id = request.query_params.get("version")
        version = None
        if version_id:
            try:
                version = SyncMappingVersion.objects.filter(pk=version_id).first()
            except (ValueError, ValidationError):
                version = None
        tags = version.extracted_fields if version is not None else []
        return Response({"tags": tags, "departments": departments, "fields": fields})


class FacilitySignatureImageView(APIView):
    """PNG preview of the hospital signature."""

    permission_classes = [IsAdmin]

    def get(self, request: Request) -> FileResponse | Response:
        facility = FacilitySignature.objects.filter(pk=1).first()
        if facility is None or not facility.signature_image:
            return Response(status=status.HTTP_404_NOT_FOUND)
        facility.signature_image.open("rb")
        return FileResponse(facility.signature_image, content_type="image/png")


class UsbSignerDownloadView(APIView):
    """Download the Windows signer script. Admin and doctor only."""

    permission_classes = [IsAdminOrDoctor]

    def get(self, request: Request) -> FileResponse | Response:
        path = Path(settings.BASE_DIR) / "nationalsync" / "data" / "viettel_ca_signer.ps1"
        if not path.is_file():
            return Response(
                {"detail": "Không tìm thấy file chương trình ký USB."},
                status=status.HTTP_404_NOT_FOUND,
            )
        payload = build_signer_command(path.read_text(encoding="utf-8"))
        return FileResponse(
            BytesIO(payload),
            as_attachment=True,
            filename=SIGNER_DOWNLOAD_NAME,
            content_type="application/octet-stream",
        )
