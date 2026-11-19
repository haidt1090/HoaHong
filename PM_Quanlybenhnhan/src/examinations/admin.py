from __future__ import annotations

from typing import Any

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpRequest, JsonResponse
from django.urls import path

from examinations.models import (
    Department,
    DepartmentField,
    DepartmentFieldAbnormal,
    DepartmentResult,
    DepartmentTemplate,
    Examination,
    ExamPackage,
    ExamPackageDepartment,
    ImportJob,
)
from examinations.widgets import GenderOverrideWidget


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "parent", "category", "is_active")
    list_filter = ("category", "is_active", "parent")
    search_fields = ("name", "code")
    autocomplete_fields = ("parent",)
    ordering = ("name",)


class DepartmentFieldInline(admin.TabularInline):
    model = DepartmentField
    fields = (
        "label",
        "key",
        "field_type",
        "input_format",
        "applies_to",
        "unit",
        "required",
        "order",
        "formula",
        "normal_range_min",
        "normal_range_max",
        "default_value",
        "gender_overrides",
        "default_price",
        "test_category",
        "options",
    )
    extra = 1
    ordering = ("order",)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj=obj, **kwargs)
        form = formset.form
        form.base_fields["formula"].widget = forms.Textarea(
            attrs={
                "placeholder": 'VD: {weight} / (({height}/100)^2) hoặc IF({bmi}<25,"Bình thường","Cao")',
                "rows": 2,
                "cols": 40,
            }
        )
        form.base_fields["gender_overrides"].widget = GenderOverrideWidget()
        return formset


@admin.register(DepartmentTemplate)
class DepartmentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "version", "created_by", "is_active")
    list_filter = ("is_active", "department")
    search_fields = ("name",)
    autocomplete_fields = ("department",)
    readonly_fields = ("created_by",)
    inlines = [DepartmentFieldInline]
    ordering = ("department__name", "name")
    actions = ["duplicate_template"]

    def save_model(
        self,
        request: HttpRequest,
        obj: DepartmentTemplate,
        form: forms.ModelForm,
        change: bool,
    ) -> None:
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Nhân bản template đã chọn")
    def duplicate_template(self, request, queryset):
        for original in queryset:
            new = DepartmentTemplate.objects.create(
                department=original.department,
                name=f"{original.name} (bản sao)",
                created_by=request.user,
            )
            # Build new field rows and track old→new field mapping
            old_to_new: dict[str, DepartmentField] = {}
            fields: list[DepartmentField] = []
            for f in original.fields.all():
                old_id = str(f.id)
                f.pk = None
                f.id = None
                f.template = new
                f.created_at = None
                f.updated_at = None
                fields.append(f)
                old_to_new[old_id] = f
            DepartmentField.objects.bulk_create(fields)

            # Also duplicate all abnormal definitions
            abnormals: list[DepartmentFieldAbnormal] = []
            for f in original.fields.prefetch_related("abnormal_definitions").all():
                new_field = old_to_new.get(str(f.id))
                if new_field is None:
                    continue
                for ad in f.abnormal_definitions.all():
                    ad.pk = None
                    ad.id = None
                    ad.field = new_field
                    ad.created_at = None
                    ad.updated_at = None
                    abnormals.append(ad)
            if abnormals:
                DepartmentFieldAbnormal.objects.bulk_create(abnormals)
        self.message_user(request, f"Đã nhân bản {queryset.count()} template.")


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    """Read-only admin view for Excel import job status and errors."""

    list_display = (
        "department",
        "exam_date",
        "status",
        "total_rows",
        "success_count",
        "updated_count",
        "skipped_count",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "department", "exam_date")
    search_fields = ("department__name", "created_by__email")
    readonly_fields = (
        "department",
        "exam_date",
        "file",
        "status",
        "total_rows",
        "success_count",
        "updated_count",
        "skipped_count",
        "errors",
        "created_by",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        return False


class ExamPackageDepartmentInlineForm(forms.ModelForm):
    """Inline form that ensures the chosen template belongs to the department."""

    class Meta:
        model = ExamPackageDepartment
        fields = "__all__"

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()
        department = cleaned.get("department")
        template = cleaned.get("template")
        if department and template and template.department_id != department.id:
            raise DjangoValidationError({"template": "Mẫu không thuộc khoa đã chọn."})
        return cleaned


class ExamPackageDepartmentInline(admin.TabularInline):
    model = ExamPackageDepartment
    form = ExamPackageDepartmentInlineForm
    extra = 1
    autocomplete_fields = ("department", "template")


@admin.register(ExamPackage)
class ExamPackageAdmin(admin.ModelAdmin):
    list_display = ("name", "exam_type", "default_package_price", "is_active")
    list_filter = ("exam_type", "is_active")
    search_fields = ("name", "description")
    inlines = [ExamPackageDepartmentInline]
    ordering = ("name",)


class DepartmentResultInline(admin.TabularInline):
    model = DepartmentResult
    extra = 0
    fields = ("department", "completed_by", "completed_at", "version")
    readonly_fields = ("department", "completed_by", "completed_at", "version")
    can_delete = False
    show_change_link = True


# ---------------------------------------------------------------------------
# DepartmentResult admin form — renders data as a dynamic table
# ---------------------------------------------------------------------------


class DepartmentResultAdminForm(forms.ModelForm):
    """
    Replaces the raw ``data`` JSONField with dynamic form fields generated
    from ``template_snapshot``. Each column in the snapshot becomes a labelled
    input (text/number/select/date/boolean/textarea), so the admin sees a
    table-like form instead of editing JSON by hand.
    """

    class Meta:
        model = DepartmentResult
        exclude = ("data",)

    _dynamic_prefix = "dr_field_"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # ``template_snapshot`` is a frozen copy — read-only here.
        if "template_snapshot" in self.fields:
            self.fields["template_snapshot"].disabled = True

        snapshot = self._resolve_snapshot(kwargs.get("instance"))
        data = self._resolve_data(kwargs.get("instance"))

        for col in snapshot:
            key = col.get("key")
            if not key:
                continue
            label_parts = [col.get("label", key)]
            unit = col.get("unit")
            if unit:
                label_parts.append(f"({unit})")
            normal_range = col.get("normal_range")
            if isinstance(normal_range, dict):
                lo = normal_range.get("min", "")
                hi = normal_range.get("max", "")
                if lo != "" or hi != "":
                    label_parts.append(f"[{lo}–{hi}]")
            display_label = " ".join(label_parts)

            field_name = f"{self._dynamic_prefix}{key}"
            field_type = col.get("type", "text")
            required = col.get("required", False)
            value = data.get(key)

            if field_type == "textarea":
                self.fields[field_name] = forms.CharField(
                    label=display_label,
                    required=required,
                    initial=value,
                    widget=forms.Textarea(attrs={"rows": 3}),
                )
            elif field_type == "number":
                self.fields[field_name] = forms.FloatField(
                    label=display_label, required=required, initial=value
                )
            elif field_type == "boolean":
                self.fields[field_name] = forms.BooleanField(
                    label=display_label, required=False, initial=bool(value)
                )
            elif field_type == "select":
                options = col.get("options", [])
                choices = [("", "---")] + [(o, o) for o in options]
                self.fields[field_name] = forms.ChoiceField(
                    label=display_label,
                    choices=choices,
                    required=required,
                    initial=value,
                )
            elif field_type == "multi_select":
                options = col.get("options", [])
                self.fields[field_name] = forms.MultipleChoiceField(
                    label=display_label,
                    choices=[(o, o) for o in options],
                    required=required,
                    initial=value if isinstance(value, list) else [],
                    widget=forms.CheckboxSelectMultiple,
                )
            elif field_type == "date":
                self.fields[field_name] = forms.DateField(
                    label=display_label,
                    required=required,
                    initial=value,
                    widget=forms.DateInput(attrs={"type": "date"}),
                )
            else:
                self.fields[field_name] = forms.CharField(
                    label=display_label, required=required, initial=value or ""
                )

    def _resolve_snapshot(
        self, instance: DepartmentResult | None
    ) -> list[dict[str, Any]]:
        if instance and instance.template_snapshot:
            return instance.template_snapshot
        initial_snapshot = self.initial.get("template_snapshot")
        if isinstance(initial_snapshot, list):
            return initial_snapshot
        return []

    def _resolve_data(self, instance: DepartmentResult | None) -> dict[str, Any]:
        if instance and instance.data:
            return instance.data
        initial_data = self.initial.get("data")
        if isinstance(initial_data, dict):
            return initial_data
        return {}

    def save(self, commit: bool = True) -> DepartmentResult:
        instance = super().save(commit=False)
        data: dict[str, Any] = {}
        snapshot = instance.template_snapshot or []
        for col in snapshot:
            key = col.get("key")
            if not key:
                continue
            field_name = f"{self._dynamic_prefix}{key}"
            if field_name in self.cleaned_data:
                data[key] = self.cleaned_data[field_name]
        if commit:
            instance.save()
            instance._sync_values(data)
        return instance


@admin.register(Examination)
class ExaminationAdmin(admin.ModelAdmin):
    list_display = (
        "patient",
        "company_name",
        "exam_type",
        "exam_date",
        "status",
        "doctor",
        "version",
    )
    list_filter = (
        "status",
        "exam_type",
        "exam_date",
        ("patient__company", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = ("patient__full_name", "patient__employee_code")
    autocomplete_fields = ("patient", "doctor", "exam_package", "company_exam_package")
    readonly_fields = ("version", "status")
    inlines = [DepartmentResultInline]
    ordering = ("-exam_date",)
    change_form_template = "admin/examinations/examination/change_form.html"

    @admin.display(description="Công ty", ordering="patient__company__name")
    def company_name(self, obj: Examination) -> str:
        """Company from patient, falling back to the assigned company package."""
        if obj.patient_id and obj.patient.company_id:
            return obj.patient.company.name
        cep = obj.company_exam_package
        if cep is not None and cep.company_id:
            return cep.company.name
        return "—"

    def get_queryset(self, request: HttpRequest):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "patient__company",
                "company_exam_package__company",
                "doctor",
            )
        )

    # -- Custom URL: return exam_type for a given exam_package id ------------

    def get_urls(self) -> list:
        custom = [
            path(
                "package-exam-type/",
                self.admin_site.admin_view(self._package_exam_type_view),
                name="examinations_examination_package_exam_type",
            ),
        ]
        return custom + super().get_urls()

    def _package_exam_type_view(self, request: HttpRequest) -> JsonResponse:
        """Return the exam_type for a given exam_package ID."""
        package_id = request.GET.get("package_id")
        if not package_id:
            return JsonResponse({"exam_type": ""})
        try:
            pkg = ExamPackage.objects.get(pk=package_id)
            return JsonResponse({"exam_type": pkg.exam_type})
        except ExamPackage.DoesNotExist:
            return JsonResponse({"exam_type": ""})


@admin.register(DepartmentResult)
class DepartmentResultAdmin(admin.ModelAdmin):
    list_display = (
        "examination",
        "department",
        "completed_by",
        "completed_at",
        "version",
    )
    list_filter = ("department",)
    search_fields = ("examination__patient__full_name",)
    autocomplete_fields = ("completed_by",)
    readonly_fields = ("version",)
    exclude = ("data", "template_snapshot")
    change_form_template = "admin/examinations/departmentresult/change_form.html"

    # -- Custom URLs for AJAX preview ----------------------------------------

    def get_urls(self) -> list:
        custom = [
            path(
                "preview-fields/",
                self.admin_site.admin_view(self._preview_fields_view),
                name="examinations_departmentresult_preview_fields",
            ),
        ]
        return custom + super().get_urls()

    def _preview_fields_view(self, request: HttpRequest) -> JsonResponse:
        """Return JSON array of fields for a given examination + department."""
        examination_id = request.GET.get("examination")
        department_id = request.GET.get("department")
        if not examination_id or not department_id:
            return JsonResponse({"fields": []})
        fields = self._resolve_fields(examination_id, department_id)
        return JsonResponse({"fields": fields})

    # -- Snapshot resolution -------------------------------------------------

    def _resolve_fields(
        self, examination_id: str, department_id: str
    ) -> list[dict[str, Any]]:
        """Look up the template snapshot for an exam+dept combo."""
        # 1) Check existing DepartmentResult (use .first() to handle duplicates)
        existing = DepartmentResult.objects.filter(
            examination_id=examination_id,
            department_id=department_id,
        ).first()
        if existing:
            return existing.template_snapshot or []
        # 2) Look up from ExamPackageDepartment binding
        exam = (
            Examination.objects.select_related("exam_package")
            .filter(pk=examination_id)
            .first()
        )
        if exam and exam.exam_package:
            binding = (
                ExamPackageDepartment.objects.select_related("template")
                .filter(exam_package=exam.exam_package, department_id=department_id)
                .first()
            )
            if binding:
                return binding.template.fields_config or []
        return []

    # -- Change form ---------------------------------------------------------

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = None
        if object_id:
            try:
                obj = self.get_object(request, object_id)
            except (self.model.DoesNotExist, ValueError):
                pass

        if obj and obj.template_snapshot:
            snapshot = obj.template_snapshot
            data = obj.data or {}
        else:
            exam_id = request.GET.get("examination", "")
            dept_id = request.GET.get("department", "")
            snapshot = (
                self._resolve_fields(exam_id, dept_id) if exam_id and dept_id else []
            )
            data = {}

        extra_context["dynamic_fields"] = [
            {
                "key": col.get("key"),
                "label": col.get("label", col.get("key")),
                "type": col.get("type", "text"),
                "unit": col.get("unit", ""),
                "normal_range": col.get("normal_range"),
                "options": col.get("options", []),
                "required": col.get("required", False),
                "value": data.get(col.get("key")),
            }
            for col in snapshot
        ]
        extra_context["preview_fields_url"] = (
            "/admin/examinations/departmentresult/preview-fields/"
        )

        return super().changeform_view(request, object_id, form_url, extra_context)

    # -- Save ----------------------------------------------------------------

    def save_model(self, request, obj, form, change):
        # Resolve snapshot for new objects (not yet in DB)
        if not obj.template_snapshot and obj.examination_id and obj.department_id:
            obj.template_snapshot = self._resolve_fields(
                str(obj.examination_id), str(obj.department_id)
            )
        # Collect dr_field_* values from POST
        snapshot = obj.template_snapshot or []
        if snapshot:
            data: dict[str, Any] = {}
            for col in snapshot:
                key = col.get("key")
                if not key:
                    continue
                field_type = col.get("type", "text")
                if field_type == "multi_select":
                    data[key] = request.POST.getlist(f"dr_field_{key}")
                    continue
                raw = request.POST.get(f"dr_field_{key}", "")
                if field_type == "number":
                    try:
                        data[key] = float(raw) if raw else None
                    except ValueError:
                        data[key] = raw
                elif field_type == "boolean":
                    data[key] = raw == "on" or raw == "true"
                else:
                    data[key] = raw
        super().save_model(request, obj, form, change)
        if snapshot:
            obj._sync_values(data)


@admin.register(DepartmentFieldAbnormal)
class DepartmentFieldAbnormalAdmin(admin.ModelAdmin):
    list_display = ("field", "direction", "label", "keyword")
    list_filter = ("direction",)
    search_fields = ("label", "field__label", "field__key")
    autocomplete_fields = ("field", "keyword")
    ordering = ("field__template__name", "field__order", "direction")


@admin.register(DepartmentField)
class DepartmentFieldAdmin(admin.ModelAdmin):
    list_display = ("label", "key", "field_type", "applies_to", "input_format", "template")
    list_filter = ("template", "field_type", "applies_to", "input_format")
    search_fields = ("label", "key", "template__name")
    autocomplete_fields = ("template",)
    ordering = ("template__name", "order")

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj=obj, **kwargs)
        form.base_fields["gender_overrides"].widget = GenderOverrideWidget()
        return form
