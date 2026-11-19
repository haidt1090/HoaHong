from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from accounts.models import Company, CompanyExamPackage
from examinations.serializers import ExamPackageSummarySerializer
from patients.models import Patient


@extend_schema_serializer(component_name="CompanyRegistry")
class CompanySerializer(serializers.ModelSerializer):
    """Full Company representation for the company registry CRUD endpoints."""

    patient_count = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "code",
            "address",
            "tax_code",
            "contact_person",
            "contact_phone",
            "contact_email",
            "is_active",
            "patient_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_patient_count(self, obj: Company) -> int:
        # Uses annotation when available (list view), falls back to a query.
        annotated = getattr(obj, "patient_count_annotated", None)
        if annotated is not None:
            return annotated
        return obj.patients.filter(is_active=True).count()


@extend_schema_serializer(component_name="CompanySummary")
class CompanySummarySerializer(serializers.ModelSerializer):
    """Lightweight company representation nested inside patient payloads."""

    class Meta:
        model = Company
        fields = ["id", "name", "code"]


class PatientSerializer(serializers.ModelSerializer):
    """Read/write serializer for Patient create, update, and list."""

    company_detail = CompanySummarySerializer(source="company", read_only=True)
    exam_status = serializers.CharField(read_only=True, allow_null=True)
    exam_done = serializers.IntegerField(read_only=True, allow_null=True)
    exam_filled = serializers.IntegerField(read_only=True, allow_null=True)
    exam_total_fields = serializers.IntegerField(read_only=True, allow_null=True)
    exam_progress = serializers.FloatField(read_only=True, allow_null=True)

    class Meta:
        model = Patient
        fields = [
            "id",
            "company",
            "company_detail",
            "employee_code",
            "full_name",
            "dob",
            "gender",
            "cccd",
            "cccd_issued_date",
            "cccd_issued_place",
            "address",
            "phone",
            "email",
            "department",
            "start_date",
            "is_active",
            "notes",
            "exam_status",
            "exam_done",
            "exam_filled",
            "exam_total_fields",
            "exam_progress",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_active", "created_at", "updated_at"]
        validators = []  # UniqueTogetherValidator removed; handled in validate()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate company / employee_code rules and uniqueness."""
        # Determine effective values (from input or existing instance)
        request_method = (
            self.context.get("request").method if self.context.get("request") else None
        )
        is_update = request_method in ("PUT", "PATCH")

        company_id = attrs.get("company")
        if is_update and "company" not in attrs and self.instance is not None:
            company_id = self.instance.company_id

        employee_code = attrs.get("employee_code")
        if is_update and "employee_code" not in attrs and self.instance is not None:
            employee_code = self.instance.employee_code

        # Rule: if company is set, employee_code is required (non-blank).
        if company_id and not employee_code:
            raise serializers.ValidationError(
                {"employee_code": "Mã nhân viên là bắt buộc khi có công ty."}
            )

        # Duplicate check: only when company IS NOT NULL
        if company_id and employee_code:
            qs = Patient.objects.filter(
                company_id=company_id, employee_code=employee_code
            )
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"employee_code": "Mã nhân viên đã tồn tại trong công ty này."}
                )

        return attrs


class ExaminationTimelineSerializer(serializers.Serializer):
    """
    Read-only summary of an examination for the patient history timeline.

    Defined here (rather than in the examinations app) so the patients app
    stays decoupled and functional before Sprint 5 lands.
    """

    id = serializers.UUIDField(read_only=True)
    exam_date = serializers.DateField(read_only=True)
    exam_type = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    conclusion = serializers.CharField(read_only=True)


class PatientDetailSerializer(PatientSerializer):
    """Patient detail including the examination history timeline."""

    examinations = serializers.SerializerMethodField()

    class Meta(PatientSerializer.Meta):
        fields = PatientSerializer.Meta.fields + ["examinations"]

    def get_examinations(self, obj: Patient) -> list[dict[str, Any]]:
        related = getattr(obj, "examinations", None)
        if related is None:
            # examinations app not installed yet (Sprint 5).
            return []
        queryset = related.all().order_by("-exam_date", "-created_at")
        return ExaminationTimelineSerializer(queryset, many=True).data


class CompanyExamPackageSerializer(serializers.ModelSerializer):
    """Serializer for CompanyExamPackage."""

    company = CompanySummarySerializer(read_only=True)
    package_detail = ExamPackageSummarySerializer(source="exam_package", read_only=True)
    total_cost = serializers.SerializerMethodField()

    class Meta:
        model = CompanyExamPackage
        fields = [
            "id",
            "company",
            "exam_package",
            "package_detail",
            "pricing_mode",
            "total_employees",
            "total_cost",
            "is_active",
            "assigned_at",
            "assigned_by",
        ]
        read_only_fields = [
            "id",
            "company",
            "package_detail",
            "total_cost",
            "assigned_at",
            "assigned_by",
        ]
        validators = []  # UniqueTogetherValidator removed; handled in validate()

    def get_total_cost(self, obj: CompanyExamPackage) -> int:
        return obj.total_cost

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        company = getattr(self.instance, "company_id", None)
        if self.context.get("view"):
            company = self.context["view"].kwargs.get("company_pk") or company
        exam_package = attrs.get("exam_package") or getattr(
            self.instance, "exam_package_id", None
        )
        if company and exam_package:
            qs = CompanyExamPackage.objects.filter(
                company_id=company, exam_package=exam_package
            )
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"exam_package": "Gói khám này đã được gán cho công ty."}
                )
        return attrs
