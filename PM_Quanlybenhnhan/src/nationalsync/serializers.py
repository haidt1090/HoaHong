"""National sync serializers — Phase 8, Sprint 16."""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from nationalsync.models import (
    SyncConfig,
    SyncFieldMapping,
    SyncJob,
    SyncMappingVersion,
)


@extend_schema_serializer(component_name="NationalSyncConfig")
class SyncConfigSerializer(serializers.ModelSerializer):
    """Read/update serializer for the singleton SyncConfig.

    Secrets are write-only: ``password`` and ``private_key`` are never
    serialized back to the client. ``is_configured``, ``password_set`` and
    ``private_key_set`` let the UI show status without exposing values.
    """

    environment_display = serializers.CharField(
        source="get_environment_display", read_only=True
    )
    api_base_url_effective = serializers.CharField(
        source="effective_api_base_url", read_only=True
    )
    is_configured = serializers.BooleanField(read_only=True)
    password_set = serializers.SerializerMethodField()
    private_key_set = serializers.SerializerMethodField()

    class Meta:
        model = SyncConfig
        fields = [
            "id",
            "environment",
            "environment_display",
            "api_base_url",
            "api_base_url_effective",
            "username",
            "password",
            "facility_code",
            "sender_id",
            "receiver_id",
            "version",
            "private_key",
            "public_key",
            "is_active",
            "is_configured",
            "password_set",
            "private_key_set",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "environment_display",
            "api_base_url_effective",
            "is_configured",
            "password_set",
            "private_key_set",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "environment": {"required": True},
            "password": {"write_only": True, "required": False, "allow_blank": True},
            "private_key": {"write_only": True, "required": False, "allow_blank": True},
        }

    def get_password_set(self, obj: SyncConfig) -> bool:
        return bool(obj.password)

    def get_private_key_set(self, obj: SyncConfig) -> bool:
        return bool(obj.private_key)

    def update(self, instance: SyncConfig, validated_data: dict) -> SyncConfig:
        # Leave secrets untouched when the client omits them.
        if "password" in validated_data and not validated_data["password"]:
            validated_data.pop("password")
        if "private_key" in validated_data and not validated_data["private_key"]:
            validated_data.pop("private_key")
        return super().update(instance, validated_data)


class SyncScopeSerializer(serializers.Serializer):
    """Request payload for ``/validate/`` and ``/trigger/``."""

    environment = serializers.ChoiceField(
        choices=SyncConfig.ENVIRONMENT_CHOICES, required=False
    )
    scope_type = serializers.ChoiceField(choices=SyncJob.SCOPE_CHOICES)
    company_id = serializers.UUIDField(required=False, allow_null=True)
    patient_id = serializers.UUIDField(required=False, allow_null=True)
    examination_id = serializers.UUIDField(required=False, allow_null=True)
    cks_nguoi_ket_luan = serializers.DictField(
        child=serializers.CharField(max_length=500000),
        required=False,
    )

    def validate_cks_nguoi_ket_luan(self, value: dict[str, str]) -> dict[str, str]:
        import base64

        cleaned: dict[str, str] = {}
        for exam_id, raw in value.items():
            text = "".join((raw or "").split())
            try:
                decoded = base64.b64decode(text, validate=True)
            except Exception as exc:
                raise serializers.ValidationError(
                    "Chữ ký USB không phải chuỗi Base64 hợp lệ."
                ) from exc
            try:
                signature_xml = decoded.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise serializers.ValidationError(
                    "Chữ ký USB phải là XML Signature dạng Base64."
                ) from exc
            if "<Signature" not in signature_xml or "xmldsig#" not in signature_xml:
                raise serializers.ValidationError(
                    "Chữ ký USB phải là XML Signature (http://www.w3.org/2000/09/xmldsig#)."
                )
            cleaned[str(exam_id)] = text
        return cleaned


class SyncJobSerializer(serializers.ModelSerializer):
    scope_type_display = serializers.CharField(
        source="get_scope_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    environment_display = serializers.SerializerMethodField()
    company_name = serializers.CharField(
        source="company.name", read_only=True, default=None
    )
    patient_name = serializers.CharField(
        source="patient.full_name", read_only=True, default=None
    )
    examination_patient = serializers.CharField(
        source="examination.patient.full_name", read_only=True, default=None
    )
    created_by_name = serializers.CharField(
        source="created_by.display_name", read_only=True, default=None
    )

    class Meta:
        model = SyncJob
        fields = [
            "id",
            "status",
            "status_display",
            "environment",
            "environment_display",
            "scope_type",
            "scope_type_display",
            "company",
            "company_name",
            "patient",
            "patient_name",
            "examination",
            "examination_patient",
            "examination_count",
            "success_count",
            "failed_count",
            "skipped_count",
            "synced_examination_ids",
            "response",
            "error_message",
            "created_by",
            "created_by_name",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_environment_display(self, obj: SyncJob) -> str:
        return dict(SyncConfig.ENVIRONMENT_CHOICES).get(obj.environment, obj.environment or "")


class SyncMappingVersionSerializer(serializers.ModelSerializer):
    """A named XML upload and whether sync currently uses it."""

    field_count = serializers.SerializerMethodField()

    class Meta:
        model = SyncMappingVersion
        fields = [
            "id",
            "name",
            "is_default",
            "source_filename",
            "field_count",
            "created_at",
        ]
        read_only_fields = fields

    def get_field_count(self, obj: SyncMappingVersion) -> int:
        return len(obj.extracted_fields or [])


class SyncFieldMappingSerializer(serializers.ModelSerializer):
    """Admin mapping of one department column key onto a national XML tag."""

    department_name = serializers.CharField(source="department.name", read_only=True)
    field_present = serializers.SerializerMethodField()

    class Meta:
        model = SyncFieldMapping
        fields = [
            "id",
            "version",
            "block",
            "xml_tag",
            "department",
            "department_name",
            "field_key",
            "alias_keys",
            "ma_dich_vu",
            "ma_chi_so",
            "field_present",
        ]
        read_only_fields = ["id", "department_name", "field_present"]

    def get_field_present(self, obj: SyncFieldMapping) -> bool:
        pairs = self.context.get("field_pairs")
        if pairs is None or obj.department_id is None:
            return False
        return (obj.department_id, obj.field_key) in pairs

    def validate(self, attrs: dict) -> dict:
        current = self.instance
        draft = SyncFieldMapping(
            version=attrs.get("version", getattr(current, "version", None)),
            block=attrs.get("block", getattr(current, "block", "")),
            xml_tag=attrs.get("xml_tag", getattr(current, "xml_tag", "")),
            department=attrs.get("department", getattr(current, "department", None)),
            field_key=attrs.get("field_key", getattr(current, "field_key", "")),
            alias_keys=attrs.get("alias_keys", getattr(current, "alias_keys", [])),
            ma_dich_vu=attrs.get("ma_dich_vu", getattr(current, "ma_dich_vu", "")),
            ma_chi_so=attrs.get("ma_chi_so", getattr(current, "ma_chi_so", "")),
        )
        if current is not None:
            draft.pk = current.pk
        try:
            draft.clean()
        except DjangoValidationError as exc:
            detail = exc.message_dict if getattr(exc, "message_dict", None) else exc.messages
            raise serializers.ValidationError(detail) from exc
        attrs["xml_tag"] = draft.xml_tag
        attrs["field_key"] = draft.field_key
        attrs["alias_keys"] = draft.alias_keys
        attrs["ma_dich_vu"] = draft.ma_dich_vu
        attrs["ma_chi_so"] = draft.ma_chi_so
        return attrs

    def create(self, validated_data: dict) -> SyncFieldMapping:
        return self._save(SyncFieldMapping(**validated_data))

    def update(self, instance: SyncFieldMapping, validated_data: dict) -> SyncFieldMapping:
        for key, value in validated_data.items():
            setattr(instance, key, value)
        return self._save(instance)

    def _save(self, instance: SyncFieldMapping) -> SyncFieldMapping:
        try:
            instance.save()
        except DjangoValidationError as exc:
            detail = exc.message_dict if getattr(exc, "message_dict", None) else exc.messages
            raise serializers.ValidationError(detail) from exc
        return instance
