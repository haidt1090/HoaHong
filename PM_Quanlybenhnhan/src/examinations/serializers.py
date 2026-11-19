from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from examinations.models import (
    Department,
    DepartmentField,
    DepartmentResult,
    DepartmentTemplate,
    Examination,
    ExamPackage,
    ExamPackageDepartment,
    ExportJob,
    ImportJob,
    normalize_gender_overrides,
)
from examinations.validators import validate_fields_config


class DepartmentSummarySerializer(serializers.ModelSerializer):
    """Lightweight department representation nested inside package payloads."""

    class Meta:
        model = Department
        fields = ["id", "name", "code", "category"]


class DepartmentSerializer(serializers.ModelSerializer):
    """CRUD serializer for medical departments."""

    parent = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        help_text="Parent department for hierarchical grouping.",
    )
    parent_detail = DepartmentSummarySerializer(source="parent", read_only=True)
    children = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "code",
            "category",
            "description",
            "is_active",
            "parent",
            "parent_detail",
            "children",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_children(self, obj):
        return DepartmentSummarySerializer(
            obj.children.filter(is_active=True), many=True
        ).data

    def validate_parent(self, value):
        if value and self.instance and value.pk == self.instance.pk:
            raise serializers.ValidationError("Không thể chọn chính mình làm khoa cha.")
        if value and self.instance:
            ancestors = value.get_ancestors()
            if self.instance in ancestors:
                raise serializers.ValidationError(
                    "Tạo vòng lặp: khoa cha đã là con/cháu của khoa này."
                )
        return value


class DepartmentFieldSerializer(serializers.ModelSerializer):
    """Nested serializer for individual field definitions in a template."""

    normal_range = serializers.JSONField(write_only=True, required=False)
    gender_overrides = serializers.JSONField(required=False)

    class Meta:
        model = DepartmentField
        fields = [
            "id",
            "key",
            "label",
            "field_type",
            "unit",
            "required",
            "order",
            "normal_range",
            "normal_range_min",
            "normal_range_max",
            "default_value",
            "gender_overrides",
            "default_price",
            "test_category",
            "options",
            "input_format",
            "applies_to",
        ]
        read_only_fields = ["id"]

    def validate_gender_overrides(self, value: Any) -> dict[str, Any]:
        try:
            return normalize_gender_overrides(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        nr = attrs.pop("normal_range", None)
        if isinstance(nr, dict):
            if "min" in nr and nr["min"] is not None:
                attrs.setdefault("normal_range_min", nr["min"])
            if "max" in nr and nr["max"] is not None:
                attrs.setdefault("normal_range_max", nr["max"])
        field_type = attrs.get(
            "field_type", getattr(self.instance, "field_type", "text")
        )
        input_format = attrs.get(
            "input_format", getattr(self.instance, "input_format", "")
        )
        if input_format == "bp_slash" and field_type not in ("text", "textarea"):
            raise serializers.ValidationError(
                {
                    "input_format": (
                        "Định dạng huyết áp (bp_slash) chỉ dùng cho trường text/textarea."
                    )
                }
            )
        return attrs


class DepartmentTemplateSerializer(serializers.ModelSerializer):
    """
    CRUD serializer for a department's tabular form definition.

    ``version`` auto-increments on content update.
    ``created_by`` is set from the request user on create.

    **v3:** ``fields`` is a write-nested array of ``DepartmentField``
    objects. ``fields_config`` is a read-only property that serializes the
    rows back into the legacy JSON array shape for the render API and
    ``DepartmentResult.template_snapshot``.
    """

    department_detail = DepartmentSummarySerializer(source="department", read_only=True)
    fields = DepartmentFieldSerializer(many=True, write_only=True, required=False)
    fields_config = serializers.SerializerMethodField()

    class Meta:
        model = DepartmentTemplate
        fields = [
            "id",
            "department",
            "department_detail",
            "name",
            "fields",
            "fields_config",
            "version",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "version",
            "fields_config",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_fields_config(self, obj: DepartmentTemplate) -> list[dict[str, Any]]:
        return obj.fields_config

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> DepartmentTemplate:
        fields_data = validated_data.pop("fields", [])
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data.setdefault("created_by", request.user)
        instance = DepartmentTemplate.objects.create(**validated_data)
        self._sync_fields(instance, fields_data)
        return instance

    @transaction.atomic
    def update(
        self, instance: DepartmentTemplate, validated_data: dict[str, Any]
    ) -> DepartmentTemplate:
        fields_data = validated_data.pop("fields", None)
        validated_data["version"] = instance.version + 1
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if fields_data is not None:
            self._sync_fields(instance, fields_data)
        return instance

    @staticmethod
    def _sync_fields(
        template: DepartmentTemplate, fields_data: list[dict[str, Any]]
    ) -> None:
        template.fields.all().delete()
        DepartmentField.objects.bulk_create(
            [
                DepartmentField(
                    template=template,
                    **{k: v for k, v in entry.items() if k != "type"},
                )
                for entry in fields_data
            ]
        )

    def validate_fields(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Validate a deep copy so the original payload is not mutated with
        # the legacy ``type`` key (which would break DepartmentField(**entry)).
        import copy

        validate_fields_config(copy.deepcopy(value))
        return value


class ExamPackageDepartmentSerializer(serializers.ModelSerializer):
    """Nested through-model entry: department + frozen template + order."""

    department_detail = DepartmentSummarySerializer(source="department", read_only=True)

    class Meta:
        model = ExamPackageDepartment
        fields = [
            "id",
            "department",
            "department_detail",
            "template",
            "order",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        template = attrs.get("template")
        department = attrs.get("department")
        if template and department and template.department_id != department.id:
            raise serializers.ValidationError(
                {"template": "Mẫu không thuộc khoa đã chọn."}
            )
        return attrs


@extend_schema_serializer(component_name="ExamPackageSummary")
class ExamPackageSummarySerializer(serializers.ModelSerializer):
    """Lightweight exam package representation for nested use."""

    class Meta:
        model = ExamPackage
        fields = ["id", "name", "exam_type", "default_package_price", "is_active"]


@extend_schema_serializer(component_name="ExamPackage")
class ExamPackageSerializer(serializers.ModelSerializer):
    """
    CRUD serializer for exam packages with nested department bindings.

    On create/update the nested ``package_departments`` list is fully
    replaced (declarative). Each entry binds a department to a specific
    template version and display order.
    """

    package_departments = ExamPackageDepartmentSerializer(many=True)

    class Meta:
        model = ExamPackage
        fields = [
            "id",
            "name",
            "description",
            "exam_type",
            "default_package_price",
            "is_active",
            "package_departments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_package_departments(
        self, value: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        seen: set[tuple[Any, Any]] = set()
        for entry in value:
            department = entry.get("department")
            template = entry.get("template")
            key = (department, template)
            if key in seen:
                raise serializers.ValidationError(
                    "Mỗi khoa chỉ được xuất hiện một lần trong gói khám."
                )
            seen.add(key)
        return value

    def _sync_departments(
        self, package: ExamPackage, departments_data: list[dict[str, Any]]
    ) -> None:
        package.package_departments.all().delete()
        ExamPackageDepartment.objects.bulk_create(
            [
                ExamPackageDepartment(
                    exam_package=package,
                    department=entry["department"],
                    template=entry["template"],
                    order=entry.get("order", 0),
                )
                for entry in departments_data
            ]
        )

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> ExamPackage:
        departments_data = validated_data.pop("package_departments", [])
        package = ExamPackage.objects.create(**validated_data)
        self._sync_departments(package, departments_data)
        return package

    @transaction.atomic
    def update(
        self, instance: ExamPackage, validated_data: dict[str, Any]
    ) -> ExamPackage:
        departments_data = validated_data.pop("package_departments", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if departments_data is not None:
            self._sync_departments(instance, departments_data)
        return instance


# ---------------------------------------------------------------------------
# Examination entry — Sprint 5
# ---------------------------------------------------------------------------


class DepartmentResultSerializer(serializers.ModelSerializer):
    """Read/write serializer for a single department's result row.

    ``fields_table`` merges each column from ``template_snapshot`` with its
    current value from ``data`` so the frontend can render a dynamic table
    (columns: label, type, unit, normal_range, value) without separately
    cross-referencing two JSON blobs.

    ``data`` is read-only — the serialization property on the model (v3).
    Writes go through the ``department`` action which calls ``_sync_values``.
    """

    department_detail = DepartmentSummarySerializer(source="department", read_only=True)
    fields_table = serializers.SerializerMethodField()
    data = serializers.SerializerMethodField()

    class Meta:
        model = DepartmentResult
        fields = [
            "id",
            "department",
            "department_detail",
            "template",
            "template_snapshot",
            "data",
            "fields_table",
            "completed_by",
            "completed_at",
            "version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "department",
            "template",
            "template_snapshot",
            "data",
            "completed_by",
            "completed_at",
            "version",
            "created_at",
            "updated_at",
        ]

    def get_data(self, obj: DepartmentResult) -> dict[str, Any]:
        return obj.data

    def get_fields_table(self, obj: DepartmentResult) -> list[dict[str, Any]]:
        """Merge template_snapshot columns with data values."""
        rows: list[dict[str, Any]] = []
        data = obj.data or {}
        for col in obj.template_snapshot or []:
            row = {**col, "value": data.get(col.get("key"))}
            rows.append(row)
        return rows


class ExaminationSerializer(serializers.ModelSerializer):
    """
    Create / read / update serializer for examinations.

    On create, one :class:`DepartmentResult` is spawned per department in the
    chosen ``exam_package`` (or the ``company_exam_package``'s package),
    freezing each department template's ``fields_config`` into
    ``template_snapshot``.
    """

    department_results = DepartmentResultSerializer(many=True, read_only=True)
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)
    employee_code = serializers.CharField(source="patient.employee_code", read_only=True, allow_null=True)
    company_name = serializers.CharField(source="patient.company.name", read_only=True, allow_null=True)
    doctor_name = serializers.SerializerMethodField()
    total_departments = serializers.SerializerMethodField()

    class Meta:
        model = Examination
        fields = [
            "id",
            "patient",
            "patient_name",
            "employee_code",
            "company_name",
            "company_exam_package",
            "exam_package",
            "exam_type",
            "exam_date",
            "consultation",
            "conclusion",
            "work_fitness",
            "classification",
            "auto_diagnosed",
            "disease",
            "total_departments",
            "doctor",
            "doctor_name",
            "status",
            "version",
            "department_results",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "patient_name",
            "doctor",
            "doctor_name",
            "status",
            "version",
            "department_results",
            "auto_diagnosed",
            "created_at",
            "updated_at",
        ]

    def get_doctor_name(self, obj: Examination) -> str:
        doctor = obj.doctor
        if doctor is None:
            return ""
        return doctor.display_name

    def get_total_departments(self, obj: Examination) -> int:
        if obj.exam_package:
            return obj.exam_package.package_departments.count()
        return 0

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        # Resolve the effective package: explicit exam_package wins, else the
        # one attached to the company_exam_package.
        if not self.instance:
            package = attrs.get("exam_package")
            company_pkg = attrs.get("company_exam_package")
            if package is None and company_pkg is not None:
                package = company_pkg.exam_package
            if package is None:
                raise serializers.ValidationError(
                    {
                        "exam_package": (
                            "Cần chọn gói khám (exam_package) hoặc "
                            "company_exam_package để tạo phiếu khám."
                        )
                    }
                )
            attrs["exam_package"] = package
        return attrs

    def _spawn_department_results(self, examination: Examination) -> None:
        """Create one DepartmentResult per department in the package (if missing)."""
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
            # Build initial data dict from default_value of each field
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
            # Seed default values for newly created results
            for result in created:
                defaults: dict = {}
                for field in result.template_snapshot or []:
                    if field.get("default_value") is not None:
                        defaults[field["key"]] = field["default_value"]
                if defaults:
                    result._sync_values(defaults)

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> Examination:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data.setdefault("doctor", request.user)
        examination = Examination.objects.create(**validated_data)
        self._spawn_department_results(examination)
        return examination

    def update(
        self, instance: Examination, validated_data: dict[str, Any]
    ) -> Examination:
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # A doctor manually editing the conclusion clears the auto-generated flag.
        manual_fields = {"work_fitness", "consultation", "conclusion", "classification", "disease"}
        if manual_fields & set(validated_data.keys()):
            instance.auto_diagnosed = False

        instance.save()
        return instance


class ImportJobSerializer(serializers.ModelSerializer):
    """Read serializer for Excel import job status."""

    department_name = serializers.CharField(source="department.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.display_name", read_only=True
    )

    class Meta:
        model = ImportJob
        fields = [
            "id",
            "department",
            "department_name",
            "exam_date",
            "status",
            "total_rows",
            "success_count",
            "updated_count",
            "skipped_count",
            "errors",
            "created_by",
            "created_by_name",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ExportJobSerializer(serializers.ModelSerializer):
    """Serializer for tracking and starting Excel exports."""

    company_name = serializers.CharField(source="company.name", read_only=True)
    exam_package_name = serializers.CharField(source="exam_package.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.display_name", read_only=True
    )
    download_url = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = ExportJob
        fields = [
            "id",
            "company",
            "company_name",
            "exam_package",
            "exam_package_name",
            "department",
            "department_name",
            "exam_date",
            "status",
            "error_message",
            "progress",
            "download_url",
            "created_by",
            "created_by_name",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "error_message",
            "progress",
            "download_url",
            "created_by",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]

    def get_download_url(self, obj: ExportJob) -> str | None:
        if obj.status == ExportJob.STATUS_COMPLETED and obj.file:
            return f"/api/export/{obj.id}/download/"
        return None

    def get_progress(self, obj: ExportJob) -> dict[str, int]:
        return {
            "current": obj.current_progress,
            "total": obj.total_progress,
        }

