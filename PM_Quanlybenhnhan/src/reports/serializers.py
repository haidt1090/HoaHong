from __future__ import annotations

from typing import Any

from django.template import TemplateSyntaxError
from rest_framework import serializers

from reports.body_builder import BodyBuilder
from reports.models import (
    DepartmentReportTemplate,
    Report,
    ReportTemplate,
    ReportTemplateItem,
)
from reports.render import BLOCKED_TAGS, get_template_engine


def _validate_template_source(value: str, field_name: str) -> str:
    """Compile an author-supplied template so syntax errors fail at save time."""
    if not value or not value.strip():
        return value
    try:
        get_template_engine().from_string(value)
    except TemplateSyntaxError as exc:
        message = str(exc)
        for tag in BLOCKED_TAGS:
            if f"'{tag}'" in message:
                raise serializers.ValidationError(
                    f"Tag {{% {tag} %}} không được phép trong template báo cáo."
                ) from exc
        raise serializers.ValidationError(f"Lỗi cú pháp: {message}") from exc
    return value


class DepartmentReportTemplateSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = DepartmentReportTemplate
        fields = [
            "id",
            "name",
            "department",
            "department_name",
            "body_html",
            "config",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_body_html(self, value: str) -> str:
        return _validate_template_source(value, "body_html")


class ReportTemplateItemSerializer(serializers.ModelSerializer):
    department_template_name = serializers.CharField(
        source="department_template.name", read_only=True
    )
    resolved_department = serializers.SerializerMethodField()

    class Meta:
        model = ReportTemplateItem
        fields = [
            "id",
            "department_template",
            "department_template_name",
            "department",
            "exam_template",
            "resolved_department",
            "order",
            "page_break_before",
        ]
        read_only_fields = ["id"]

    def get_resolved_department(self, obj: ReportTemplateItem) -> str | None:
        dept_id = obj.resolved_department_id
        return str(dept_id) if dept_id else None

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        dept_template = attrs.get("department_template") or getattr(
            self.instance, "department_template", None
        )
        department = attrs.get("department", getattr(self.instance, "department", None))
        exam_template = attrs.get(
            "exam_template", getattr(self.instance, "exam_template", None)
        )
        resolved = department or (dept_template.department if dept_template else None)
        if exam_template and resolved and exam_template.department_id != resolved.id:
            raise serializers.ValidationError(
                {"exam_template": ("Mẫu nhập liệu không thuộc khoa đã chọn.")}
            )
        return attrs


class ReportTemplateSerializer(serializers.ModelSerializer):
    items = ReportTemplateItemSerializer(many=True, required=False)
    logo_url = serializers.CharField(read_only=True)

    class Meta:
        model = ReportTemplate
        fields = [
            "id",
            "name",
            "description",
            "report_type",
            "header_xlsx",
            "footer_xlsx",
            "body_type",
            "body_html",
            "body_config",
            "extra_css",
            "page_size",
            "logo",
            "logo_url",
            "is_default",
            "is_active",
            "items",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "logo_url", "created_by", "created_at", "updated_at"]

    def _validate_xlsx(self, value: Any) -> Any:
        if not value:
            return value
        name = getattr(value, "name", "") or ""
        if not str(name).lower().endswith(".xlsx"):
            raise serializers.ValidationError("Chỉ chấp nhận file Excel (.xlsx).")
        return value

    def validate_header_xlsx(self, value: Any) -> Any:
        return self._validate_xlsx(value)

    def validate_footer_xlsx(self, value: Any) -> Any:
        return self._validate_xlsx(value)

    def validate_body_html(self, value: str) -> str:
        return _validate_template_source(value, "body_html")

    def validate_body_type(self, value: str) -> str:
        if value not in BodyBuilder.REGISTRY:
            raise serializers.ValidationError(
                f"body_type không hợp lệ. Chọn một trong: {', '.join(BodyBuilder.available())}"
            )
        return value

    def validate_body_config(self, value: Any) -> Any:
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("body_config phải là một object JSON.")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Reject department items on a body_type that will never render them.

        Only the ``department_templates`` body function iterates
        ``ReportTemplate.items``. Handles PATCH in both directions: changing
        ``body_type`` on a template that already has items, and adding items to
        a template whose stored ``body_type`` ignores them.
        """
        body_type = attrs.get(
            "body_type",
            getattr(
                self.instance, "body_type", ReportTemplate.BODY_DEPARTMENT_TEMPLATES
            ),
        )
        if body_type == ReportTemplate.BODY_DEPARTMENT_TEMPLATES:
            body_html = attrs.get(
                "body_html",
                getattr(self.instance, "body_html", "") or "",
            )
            if body_html and body_html.strip():
                raise serializers.ValidationError(
                    {
                        "body_html": (
                            "body_html chỉ có tác dụng với 4 kiểu body_type "
                            "(bảng ngang, bảng máu, thống kê, chi phí). Với "
                            "“Ghép template theo khoa” thì dùng template của "
                            "từng khoa ở DepartmentReportTemplate."
                        )
                    }
                )
            return attrs

        if "items" in attrs:
            item_count = len(attrs["items"] or [])
            field = "items"
        elif self.instance is not None:
            item_count = self.instance.items.count()
            field = "body_type"
        else:
            return attrs

        if item_count:
            label = dict(ReportTemplate.BODY_TYPE_CHOICES).get(body_type, body_type)
            raise serializers.ValidationError(
                {
                    field: (
                        f"body_type '{body_type}' ({label}) không render template "
                        f"khoa, nhưng đang có {item_count} template khoa được gắn. "
                        "Dùng body_type 'department_templates', hoặc bỏ items."
                    )
                }
            )
        return attrs

    def create(self, validated_data: dict[str, Any]) -> ReportTemplate:
        items = validated_data.pop("items", [])
        template = ReportTemplate.objects.create(**validated_data)
        self._sync_items(template, items)
        return template

    def update(
        self, instance: ReportTemplate, validated_data: dict[str, Any]
    ) -> ReportTemplate:
        items = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items is not None:
            instance.items.all().delete()
            self._sync_items(instance, items)
        return instance

    @staticmethod
    def _sync_items(template: ReportTemplate, items: list[dict[str, Any]]) -> None:
        for index, item in enumerate(items):
            ReportTemplateItem.objects.create(
                report_template=template,
                department_template=item["department_template"],
                department=item.get("department"),
                # Must be forwarded: without it an API-created item loses the
                # data-entry template pin and renders every result for the
                # department (Sprint 4a duplicate bindings).
                exam_template=item.get("exam_template"),
                order=item.get("order", index),
                page_break_before=item.get("page_break_before", False),
            )


class ReportTemplateListSerializer(serializers.ModelSerializer):
    """Lightweight payload for the report-generation dropdown."""

    item_count = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = ReportTemplate
        fields = [
            "id",
            "name",
            "description",
            "report_type",
            "body_type",
            "page_size",
            "is_default",
            "is_active",
            "item_count",
        ]


class ReportSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    template_name = serializers.CharField(source="template.name", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    exam_package_name = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            "id",
            "company",
            "company_name",
            "exam_package_name",
            "report_type",
            "output_format",
            "template",
            "template_name",
            "status",
            "parameters",
            "file_url",
            "error_message",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "file_url",
            "error_message",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_file_url(self, obj: Report) -> str | None:
        if not obj.file:
            return None
        request = self.context.get("request")
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url

    def get_exam_package_name(self, obj: Report) -> str:
        exam_package_id = (obj.parameters or {}).get("exam_package_id")
        if not exam_package_id:
            return ""
        from examinations.models import ExamPackage

        name = (
            ExamPackage.objects.filter(id=exam_package_id)
            .values_list("name", flat=True)
            .first()
        )
        return name or ""


class GenerateReportSerializer(serializers.Serializer):
    company_id = serializers.UUIDField()
    exam_package_id = serializers.UUIDField()
    exam_date = serializers.DateField(required=False, default=None, allow_null=True)
    report_type = serializers.ChoiceField(choices=Report.REPORT_TYPE_CHOICES)
    output_format = serializers.ChoiceField(
        choices=Report.FORMAT_CHOICES, default=Report.FORMAT_EXCEL
    )
    template_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    use_default_template = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        template_id = attrs.get("template_id")
        if template_id:
            try:
                template = ReportTemplate.objects.get(id=template_id, is_active=True)
            except ReportTemplate.DoesNotExist:
                raise serializers.ValidationError(
                    {"template_id": "Template không tồn tại hoặc đã bị vô hiệu hoá."}
                ) from None
            attrs["template"] = template
        else:
            attrs["template"] = None
        return attrs


class TemplatePreviewSerializer(serializers.Serializer):
    """Payload for the template preview endpoints."""

    company_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    exam_package_id = serializers.UUIDField(
        required=False, allow_null=True, default=None
    )
    exam_date = serializers.DateField(required=False, allow_null=True, default=None)
    limit = serializers.IntegerField(
        required=False, default=3, min_value=1, max_value=50
    )
    output_format = serializers.ChoiceField(
        choices=[("html", "HTML")], default="html"
    )
    # Unsaved overrides so the admin editor can preview before saving.
    body_html = serializers.CharField(required=False, allow_blank=True, default=None)
    department_id = serializers.UUIDField(required=False, allow_null=True, default=None)
