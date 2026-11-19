from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from reports.body_builder import BodyBuilder
from reports.models import (
    DepartmentReportTemplate,
    EmployeeExamReport,
    Report,
    ReportTemplate,
    ReportTemplateItem,
)
from reports.preview import PreviewDataUnavailable, build_preview_dataset
from reports.render import (
    TemplateRenderError,
    build_context,
    build_department_context,
    build_document,
    render_fragment,
    render_report,
)
from reports.shortcodes import (
    HTML_ATTRIBUTE_GUIDE,
    HTML_GUIDE_NOTES,
    HTML_TAG_GUIDE,
    REPORT_VARIABLES,
    TEMPLATE_CONCEPTS,
    tag_catalog,
    variable_groups_for,
)
from reports.widgets import PrettyJSONWidget, TemplateEditorWidget

DEPARTMENT_VARIABLE_GROUPS = variable_groups_for(department=True)


class DepartmentReportTemplateForm(forms.ModelForm):
    class Meta:
        model = DepartmentReportTemplate
        fields = "__all__"
        widgets = {
            "body_html": TemplateEditorWidget(
                attrs={"rows": 25},
                variable_groups=DEPARTMENT_VARIABLE_GROUPS,
                preview_kind="department",
            ),
            "config": PrettyJSONWidget(),
        }

    def clean_body_html(self) -> str:
        from reports.serializers import _validate_template_source

        value = self.cleaned_data["body_html"]
        try:
            return _validate_template_source(value, "body_html")
        except Exception as exc:  # DRF ValidationError → form error
            raise forms.ValidationError(_first_message(exc)) from exc


class ReportTemplateForm(forms.ModelForm):
    class Meta:
        model = ReportTemplate
        fields = "__all__"
        widgets = {
            "extra_css": forms.Textarea(attrs={"rows": 8, "class": "vLargeTextField"}),
            "body_config": PrettyJSONWidget(),
            "body_html": TemplateEditorWidget(
                attrs={"rows": 30},
                variable_groups=REPORT_VARIABLES,
                preview_kind="report",
            ),
        }

    def _clean_template(self, field_name: str) -> str:
        from reports.serializers import _validate_template_source

        value = self.cleaned_data[field_name]
        try:
            return _validate_template_source(value, field_name)
        except Exception as exc:
            raise forms.ValidationError(_first_message(exc)) from exc

    def clean_body_html(self) -> str:
        return self._clean_template("body_html")

    def clean_header_xlsx(self):
        return _validate_xlsx_upload(self.cleaned_data.get("header_xlsx"))

    def clean_footer_xlsx(self):
        return _validate_xlsx_upload(self.cleaned_data.get("footer_xlsx"))

    def clean(self):
        cleaned = super().clean()
        body_type = cleaned.get("body_type")
        if body_type and body_type not in BodyBuilder.REGISTRY:
            self.add_error(
                "body_type",
                f"Chưa có body function cho '{body_type}'.",
            )
        return cleaned


def _validate_xlsx_upload(value):
    """Accept only .xlsx uploads (or empty / clearing the field)."""
    if not value or value is False:
        return value
    name = getattr(value, "name", "") or ""
    if not name.lower().endswith(".xlsx"):
        raise forms.ValidationError("Chỉ chấp nhận file Excel (.xlsx).")
    return value


def template_guide_view(request):
    """Staff help page: variables + callable tags for report authors."""
    site = getattr(request, "admin_site", None) or admin.site
    context = {
        **site.each_context(request),
        "title": "Hướng dẫn mã template",
        "concepts": TEMPLATE_CONCEPTS,
        "tags": tag_catalog(),
        "groups": REPORT_VARIABLES,
        "html_tags": HTML_TAG_GUIDE,
        "html_attributes": HTML_ATTRIBUTE_GUIDE,
        "html_notes": HTML_GUIDE_NOTES,
    }
    return TemplateResponse(request, "admin/reports/template_guide.html", context)


def _first_message(exc: Exception) -> str:
    detail = getattr(exc, "detail", None)
    if isinstance(detail, (list, tuple)) and detail:
        return str(detail[0])
    if isinstance(detail, dict) and detail:
        first = next(iter(detail.values()))
        return str(first[0] if isinstance(first, (list, tuple)) else first)
    return str(detail or exc)


class ReportTemplateItemInlineFormSet(forms.BaseInlineFormSet):
    """
    Reject department items on a body_type that will never render them.

    Only the ``department_templates`` body function iterates
    ``ReportTemplate.items``; attaching them to any other body type used to
    save rows that silently vanished from the output.

    Django validates the parent ModelForm before constructing inline formsets
    (``ModelAdmin._changeform_view``), so ``self.instance.body_type`` already
    holds the value being submitted rather than the stored one.
    """

    def clean(self) -> None:
        super().clean()

        body_type = getattr(self.instance, "body_type", None)
        if not body_type or body_type == ReportTemplate.BODY_DEPARTMENT_TEMPLATES:
            return

        kept = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            if form.cleaned_data.get("department_template"):
                kept += 1
        if not kept:
            return

        label = dict(ReportTemplate.BODY_TYPE_CHOICES).get(body_type, body_type)
        raise forms.ValidationError(
            f"Thân báo cáo đang là “{label}” nên các template khoa bên dưới sẽ "
            "KHÔNG được render. Hãy đổi “Kiểu thân báo cáo” sang “Ghép template "
            "theo khoa”, hoặc xoá các dòng template khoa."
        )


class ReportTemplateItemInline(admin.TabularInline):
    model = ReportTemplateItem
    formset = ReportTemplateItemInlineFormSet
    extra = 1
    ordering = ["order"]
    autocomplete_fields = ["department_template", "department", "exam_template"]
    fields = [
        "order",
        "department_template",
        "department",
        "exam_template",
        "page_break_before",
    ]


@admin.register(DepartmentReportTemplate)
class DepartmentReportTemplateAdmin(admin.ModelAdmin):
    form = DepartmentReportTemplateForm
    change_list_template = "admin/reports/departmentreporttemplate/change_list.html"
    list_display = ("name", "department", "is_active", "preview_link", "updated_at")
    list_filter = ("is_active", "department")
    search_fields = ("name", "department__name")
    autocomplete_fields = ["department"]
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "department", "is_active")}),
        ("Nội dung", {"fields": ("body_html", "config")}),
        (
            "Hệ thống",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
    actions = ["duplicate_template"]

    @admin.display(description="Xem trước")
    def preview_link(self, obj: DepartmentReportTemplate) -> str:
        url = reverse("admin:reports_departmentreporttemplate_preview", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">Xem trước</a>', url)

    def get_urls(self):
        return [
            path(
                "<uuid:pk>/preview/",
                self.admin_site.admin_view(self.preview_view),
                name="reports_departmentreporttemplate_preview",
            ),
            *super().get_urls(),
        ]

    def preview_view(self, request, pk):
        template = self.get_object(request, pk)
        if template is None:
            return HttpResponse("Không tìm thấy template.", status=404)
        try:
            dataset = build_preview_dataset(limit=2)
        except PreviewDataUnavailable as exc:
            return HttpResponse(str(exc), status=400)

        base_context = build_context(dataset)
        blocks = []
        try:
            for patient in dataset.patients:
                departments = (
                    patient.departments_for(str(template.department_id))
                    if template.department_id
                    else patient.departments
                )
                for department in departments or [None]:
                    context = build_department_context(
                        patient, department, base_context, template.config or {}
                    )
                    blocks.append(
                        "<section>"
                        + render_fragment(
                            template.body_html, context, label=template.name
                        )
                        + "</section>"
                    )
        except TemplateRenderError as exc:
            return HttpResponse(f"<pre>{exc}</pre>", status=400)

        html = build_document(
            header=f"<h2>{template.name}</h2>",
            body="".join(blocks) or '<p class="empty">Không có dữ liệu.</p>',
            footer="",
            page_size=ReportTemplate.PAGE_A4_PORTRAIT,
            title=f"Xem trước — {template.name}",
        )
        return HttpResponse(html)

    @admin.action(description="Nhân bản template đã chọn")
    def duplicate_template(self, request, queryset):
        count = 0
        for template in queryset:
            template.pk = None
            template.id = None
            template.name = f"{template.name} (bản sao)"
            template.save()
            count += 1
        self.message_user(request, f"Đã nhân bản {count} template.", messages.SUCCESS)


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    form = ReportTemplateForm
    inlines = [ReportTemplateItemInline]
    # Custom change form that lifts the "Report template items" inline above
    # the layout/header/footer fieldsets (see the template's block reordering).
    change_form_template = "admin/reports/reporttemplate/change_form.html"
    change_list_template = "admin/reports/reporttemplate/change_list.html"
    # How many fieldsets render ABOVE the inline; the rest render below it.
    # 0=basic, 1=header, 2=footer → above; 3=body_html, 4=layout, 5=system → below.
    rt_inline_split = 3
    list_display = (
        "name",
        "report_type",
        "body_type",
        "items_summary",
        "page_size",
        "is_default",
        "is_active",
        "preview_link",
    )
    list_filter = ("report_type", "body_type", "is_default", "is_active")
    search_fields = ("name", "description")
    readonly_fields = (
        "created_by",
        "created_at",
        "updated_at",
        "logo_preview",
        "body_type_help",
    )
    # ``body_type`` lives in the first fieldset, not next to the body content.
    # It is a structural choice (it decides whether the department items inline
    # renders at all), and the header/footer editors are several hundred pixels
    # tall — putting it between them pushed it below the fold.
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "description",
                    "report_type",
                    "body_type",
                    "body_type_help",
                    "body_config",
                    "is_default",
                    "is_active",
                )
            },
        ),
        ("Đầu trang", {"fields": ("header_xlsx",)}),
        ("Chân trang", {"fields": ("footer_xlsx",)}),
        # ── inline renders here (rt_inline_split = 3) ──
        (
            "Thân báo cáo (template HTML)",
            {
                "fields": ("body_html",),
                "description": (
                    "Ghi đè phần thân bằng HTML. Để trống = dùng code Python "
                    "mặc định. Có tác dụng với 4 kiểu body_type."
                ),
            },
        ),        (
            "Bố cục",
            {"fields": ("page_size", "logo", "logo_preview", "extra_css")},
        ),
        (
            "Hệ thống",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
    actions = ["duplicate_template"]

    @admin.display(description="Thân báo cáo dùng gì?")
    def body_type_help(self, obj: ReportTemplate) -> str:
        """Spell out whether the current body_type reads the items inline."""
        if obj.pk is None:
            # Static literal with no interpolation: format_html() without args
            # is deprecated (RemovedInDjango60Warning).
            return mark_safe(  # hardcoded literal, no user input
                '<span style="color:#666">Chọn <b>“Ghép template theo khoa”</b> '
                "nếu muốn gắn các template khoa ở mục <i>Report template items</i> "
                "bên dưới. Các kiểu khác dựng bảng sẵn và bỏ qua mục đó.</span>"
            )

        count = obj.items.count()
        if obj.uses_department_templates:
            parts: list[str] = [
                format_html(
                    '<span style="color:#0a0">&#10003; Đang ghép <b>{}</b> template khoa</span>'
                    '<span style="color:#666"> — xem mục <i>Report template items</i> bên dưới.</span>',
                    count,
                ),
            ]
            if obj.wastes_body_html:
                parts.append(
                    mark_safe(  # static literal, no user input
                        '<br><span style="color:#b00;font-weight:bold">'
                        "&#9888; “Thân báo cáo (template HTML)” đang có nội dung "
                        "nhưng “Ghép template theo khoa” không đọc trường này. "
                        "Nội dung đó sẽ KHÔNG xuất hiện trong báo cáo.</span>"
                    )
                )
            return mark_safe("".join(parts))

        label = obj.get_body_type_display()
        if count:
            return format_html(
                '<span style="color:#b00;font-weight:bold">&#9888; “{}” không đọc '
                "template khoa, nhưng đang có {} template khoa được gắn — chúng sẽ "
                "KHÔNG xuất hiện trong báo cáo.</span>",
                label,
                count,
            )
        return format_html(
            '<span style="color:#666">“{}” dựng bảng bằng code, không dùng '
            "template khoa. Mục <i>Report template items</i> bên dưới sẽ bị bỏ qua.</span>",
            label,
        )

    @admin.display(description="Template khoa")
    def items_summary(self, obj: ReportTemplate) -> str:
        """Flag templates whose attached department items are never rendered."""
        count = obj.items.count()
        if obj.uses_department_templates:
            return f"{count} khoa" if count else "— (chưa gắn khoa)"
        if count:
            return format_html(
                '<span style="color:#b00;font-weight:bold" title="{}">'
                "&#9888; {} khoa bị bỏ qua</span>",
                "body_type hiện tại không render template khoa.",
                count,
            )
        return "—"

    @admin.display(description="Logo")
    def logo_preview(self, obj: ReportTemplate) -> str:
        if not obj.logo_url:
            return "—"
        return format_html(
            '<img src="{}" style="max-height:80px;border:1px solid #ddd">', obj.logo_url
        )

    @admin.display(description="Xem trước")
    def preview_link(self, obj: ReportTemplate) -> str:
        url = reverse("admin:reports_reporttemplate_preview", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">Xem trước</a>', url)

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        # Consumed by change_form.html to decide where the inline goes.
        context["rt_inline_split"] = self.rt_inline_split
        return super().render_change_form(
            request, context, add=add, change=change, form_url=form_url, obj=obj
        )

    def get_urls(self):
        return [
            path(
                "huong-dan/",
                self.admin_site.admin_view(template_guide_view),
                name="reports_template_guide",
            ),
            path(
                "<uuid:pk>/preview/",
                self.admin_site.admin_view(self.preview_view),
                name="reports_reporttemplate_preview",
            ),
            *super().get_urls(),
        ]

    def preview_view(self, request, pk):
        template = self.get_object(request, pk)
        if template is None:
            return HttpResponse("Không tìm thấy template.", status=404)
        try:
            dataset = build_preview_dataset(
                company_id=request.GET.get("company_id"),
                exam_package_id=request.GET.get("exam_package_id"),
                limit=int(request.GET.get("limit", 3)),
            )
        except PreviewDataUnavailable as exc:
            return HttpResponse(str(exc), status=400)

        try:
            html = render_report(template, dataset)
        except (TemplateRenderError, ValueError) as exc:
            return HttpResponse(f"<pre>{exc}</pre>", status=400)

        orphaned = template.orphaned_item_count()
        if orphaned:
            label = dict(ReportTemplate.BODY_TYPE_CHOICES).get(
                template.body_type, template.body_type
            )
            banner = (
                '<div style="background:#fde7e7;border:1px solid #b00;color:#900;'
                'padding:8px 12px;margin:0 0 8px;font:13px system-ui,sans-serif">'
                f"<b>&#9888; {orphaned} template khoa không được render.</b> "
                f"Kiểu thân báo cáo đang là “{label}”. Đổi sang “Ghép template "
                "theo khoa” để các khoa xuất hiện trong báo cáo."
                "</div>"
            )
            html = html.replace("<body>", "<body>" + banner, 1)
        return HttpResponse(html)

    @admin.action(description="Nhân bản template (kèm các khoa)")
    def duplicate_template(self, request, queryset):
        count = 0
        for template in queryset:
            items = list(template.items.all())
            template.pk = None
            template.id = None
            template.name = f"{template.name} (bản sao)"
            template.is_default = False
            template.save()
            for item in items:
                ReportTemplateItem.objects.create(
                    report_template=template,
                    department_template=item.department_template,
                    department=item.department,
                    order=item.order,
                    page_break_before=item.page_break_before,
                )
            count += 1
        self.message_user(request, f"Đã nhân bản {count} template.", messages.SUCCESS)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "report_type",
        "template",
        "output_format",
        "status",
        "created_at",
    )
    list_filter = ("report_type", "output_format", "status", "template")
    search_fields = ("company__name",)
    autocomplete_fields = ["company", "template"]
    readonly_fields = ("status", "error_message", "file", "created_at", "updated_at")


@admin.register(EmployeeExamReport)
class EmployeeExamReportAdmin(admin.ModelAdmin):
    list_display = (
        "employee_name",
        "exam_date_display",
        "status",
        "public_link",
        "password_display",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("examination__patient__full_name", "examination__patient__employee_code")
    readonly_fields = (
        "status",
        "error_message",
        "public_link",
        "password_display",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (None, {"fields": ("examination", "template", "status", "error_message")}),
        (
            "Thông tin công khai",
            {"fields": ("public_link", "password_display")},
        ),
        ("Hệ thống", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Nhân viên")
    def employee_name(self, obj: EmployeeExamReport) -> str:
        p = obj.examination.patient
        return f"{p.full_name} ({p.employee_code})"

    @admin.display(description="Ngày khám")
    def exam_date_display(self, obj: EmployeeExamReport) -> str:
        return obj.examination.exam_date.strftime("%d/%m/%Y")

    @admin.display(description="Link xem")
    def public_link(self, obj: EmployeeExamReport) -> str:
        if not obj.public_id:
            return "—"
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            obj.public_url,
            obj.public_url,
        )

    @admin.display(description="Mật khẩu")
    def password_display(self, obj: EmployeeExamReport) -> str:
        return obj.password
