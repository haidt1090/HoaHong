from __future__ import annotations

import uuid
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import BaseModel

# ---------------------------------------------------------------------------
# Shared choice constants
#
# Declared at module level so ``ReportTemplate`` (defined before ``Report``)
# can reference them without a forward reference.
# ---------------------------------------------------------------------------

REPORT_CLINICAL_DETAIL = "clinical_detail"
REPORT_COMPANY_SUMMARY = "company_summary"
REPORT_OCCUPATIONAL = "occupational"
REPORT_COST = "cost"

REPORT_TYPE_CHOICES = [
    (REPORT_CLINICAL_DETAIL, "Báo Cáo Chi Tiết"),
    (REPORT_COMPANY_SUMMARY, "Báo Cáo Tổng Hợp Công Ty"),
    (REPORT_OCCUPATIONAL, "Báo Cáo Bệnh Nghề Nghiệp"),
    (REPORT_COST, "Báo Cáo Chi Phí"),
]


class DepartmentReportTemplate(BaseModel):
    """
    A reusable HTML fragment rendering one department's results.

    ``body_html`` is a Django template string evaluated with a department-level
    context (see ``reports.render.build_department_context``). When
    ``department`` is null the template is *global* and can be attached to any
    department via :class:`ReportTemplateItem`.
    """

    name = models.CharField(max_length=255)
    department = models.ForeignKey(
        "examinations.Department",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="report_templates",
        help_text="Khoa áp dụng. Để trống = template dùng chung cho mọi khoa.",
    )
    body_html = models.TextField(
        blank=True,
        help_text="Django template. Biến: {{ department.name }}, {% for field in fields %}…",
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Tham số bổ sung, được đưa vào context dưới tên {{ config }}.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["department__name", "name"]
        verbose_name = "Department report template"
        verbose_name_plural = "Department report templates"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "department"],
                name="unique_dept_report_template_name",
            )
        ]

    def __str__(self) -> str:
        if self.department_id:
            return f"{self.name} ({self.department.name})"
        return f"{self.name} (dùng chung)"


class ReportTemplate(BaseModel):
    """Composite template: header + body + footer."""

    BODY_DEPARTMENT_TEMPLATES = "department_templates"
    BODY_CLINICAL_DETAIL_TABLE = "clinical_detail_table"
    BODY_CLINICAL_DETAIL_BLOOD_TEST = "clinical_detail_blood_test"
    BODY_SUMMARY_STATS = "summary_stats"
    BODY_COST_BREAKDOWN = "cost_breakdown"

    BODY_TYPE_CHOICES = [
        (BODY_DEPARTMENT_TEMPLATES, "Ghép template theo khoa"),
        (BODY_CLINICAL_DETAIL_TABLE, "Bảng chi tiết ngang (1 dòng/NV)"),
        (BODY_CLINICAL_DETAIL_BLOOD_TEST, "Bảng xét nghiệm máu dọc"),
        (BODY_SUMMARY_STATS, "Thống kê tổng hợp"),
        (BODY_COST_BREAKDOWN, "Bảng chi phí"),
    ]

    PAGE_A4_PORTRAIT = "A4 portrait"
    PAGE_A4_LANDSCAPE = "A4 landscape"
    PAGE_A3_LANDSCAPE = "A3 landscape"

    PAGE_SIZE_CHOICES = [
        (PAGE_A4_PORTRAIT, "A4 dọc"),
        (PAGE_A4_LANDSCAPE, "A4 ngang"),
        (PAGE_A3_LANDSCAPE, "A3 ngang"),
    ]

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    report_type = models.CharField(
        max_length=30,
        choices=REPORT_TYPE_CHOICES,
        default=REPORT_CLINICAL_DETAIL,
    )
    header_xlsx = models.FileField(
        upload_to="report_templates/headers/",
        null=True,
        blank=True,
        help_text="File Excel (.xlsx) đầu trang — giữ nguyên format/style khi ghép vào báo cáo.",
    )
    footer_xlsx = models.FileField(
        upload_to="report_templates/footers/",
        null=True,
        blank=True,
        help_text="File Excel (.xlsx) chân trang — giữ nguyên format/style khi ghép vào báo cáo.",
    )
    body_type = models.CharField(
        max_length=40,
        choices=BODY_TYPE_CHOICES,
        default=BODY_DEPARTMENT_TEMPLATES,
    )
    body_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Tham số cho body function (vd: {'columns': ['hbg','wbc']}).",
    )
    body_html = models.TextField(
        blank=True,
        help_text=(
            "Template Django cho phần thân (chỉ dùng khi body_type không phải "
            "'department_templates'). Để trống = dùng code Python mặc định."
        ),
    )
    extra_css = models.TextField(
        blank=True,
        help_text="CSS bổ sung, chèn vào thẻ style của tài liệu.",
    )
    page_size = models.CharField(
        max_length=20, choices=PAGE_SIZE_CHOICES, default=PAGE_A4_LANDSCAPE
    )
    logo = models.ImageField(upload_to="report_templates/logos/", null=True, blank=True)
    department_templates = models.ManyToManyField(
        DepartmentReportTemplate,
        through="ReportTemplateItem",
        related_name="report_templates",
        blank=True,
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Template mặc định cho loại báo cáo này.",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_report_templates",
    )

    class Meta:
        ordering = ["report_type", "name"]
        verbose_name = "Report template"
        verbose_name_plural = "Report templates"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            # Only one default per report_type.
            ReportTemplate.objects.filter(report_type=self.report_type).exclude(
                pk=self.pk
            ).update(is_default=False)

    @property
    def uses_department_templates(self) -> bool:
        """Whether ``body_type`` actually renders :class:`ReportTemplateItem` rows."""
        return self.body_type == self.BODY_DEPARTMENT_TEMPLATES

    def orphaned_item_count(self) -> int:
        """
        Number of attached department templates that ``body_type`` will ignore.

        Items are only rendered by the ``department_templates`` body function.
        Attaching them to any other body type stores rows that silently never
        reach the output, which is a confusing failure mode — callers use this
        to warn (see ``reports.admin`` and ``ReportTemplateSerializer``).
        """
        if self.uses_department_templates or not self.pk:
            return 0
        return self.items.count()

    @property
    def has_orphaned_items(self) -> bool:
        return self.orphaned_item_count() > 0

    @property
    def wastes_body_html(self) -> bool:
        """
        ``body_html`` is only rendered by the four coded body types. When
        ``body_type`` is ``department_templates`` the field is silently
        ignored — this property flags that misconfiguration so the admin
        and API can warn.
        """
        return self.body_type == self.BODY_DEPARTMENT_TEMPLATES and bool(
            self.body_html and self.body_html.strip()
        )

    @property
    def logo_url(self) -> str:
        try:
            return self.logo.url if self.logo else ""
        except ValueError:
            return ""


class ReportTemplateItem(BaseModel):
    """Ordered binding of a :class:`DepartmentReportTemplate` into a composite."""

    report_template = models.ForeignKey(
        ReportTemplate, on_delete=models.CASCADE, related_name="items"
    )
    department_template = models.ForeignKey(
        DepartmentReportTemplate, on_delete=models.CASCADE, related_name="items"
    )
    department = models.ForeignKey(
        "examinations.Department",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="report_template_items",
        help_text=(
            "Khoa cụ thể để lấy dữ liệu. Để trống = tự khớp theo "
            "department của department_template."
        ),
    )
    exam_template = models.ForeignKey(
        "examinations.DepartmentTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="report_template_items",
        help_text=(
            "Chỉ lấy kết quả của mẫu nhập liệu này. Cần thiết khi một khoa "
            "được gán nhiều mẫu trong cùng gói khám (vd: XN máu / XN nước tiểu)."
        ),
    )
    order = models.IntegerField(default=0)
    page_break_before = models.BooleanField(default=False)

    class Meta:
        ordering = ["order"]
        verbose_name = "Report template item"
        verbose_name_plural = "Report template items"

    def __str__(self) -> str:
        return f"{self.report_template.name} · {self.department_template.name}"

    def clean(self) -> None:
        super().clean()
        # A null resolved department is legitimate: it marks a "global" block
        # (patient header, conclusion table) that renders once per patient with
        # no department context. Only the department/template pairing is checked.
        if self.exam_template_id:
            resolved = self.resolved_department_id
            if resolved and self.exam_template.department_id != resolved:
                raise ValidationError(
                    {"exam_template": "Mẫu nhập liệu không thuộc khoa đã chọn."}
                )

    @property
    def resolved_department_id(self):
        """Department used to source data: explicit override, else the template's own."""
        return self.department_id or self.department_template.department_id


class Report(BaseModel):
    STATUS_PROCESSING = "processing"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PROCESSING, "Đang xử lý"),
        (STATUS_DONE, "Hoàn thành"),
        (STATUS_FAILED, "Lỗi"),
    ]

    FORMAT_EXCEL = "xlsx"
    FORMAT_HTML = "html"
    FORMAT_CHOICES = [
        (FORMAT_EXCEL, "Excel"),
        (FORMAT_HTML, "HTML"),
    ]

    # Re-exported as class attributes for backwards compatibility with the
    # existing ``Report.REPORT_*`` call sites across views/tasks/tests.
    REPORT_CLINICAL_DETAIL = REPORT_CLINICAL_DETAIL
    REPORT_COMPANY_SUMMARY = REPORT_COMPANY_SUMMARY
    REPORT_OCCUPATIONAL = REPORT_OCCUPATIONAL
    REPORT_COST = REPORT_COST
    REPORT_TYPE_CHOICES = REPORT_TYPE_CHOICES

    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE, related_name="reports"
    )
    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES)
    output_format = models.CharField(
        max_length=5, choices=FORMAT_CHOICES, default=FORMAT_EXCEL
    )
    template = models.ForeignKey(
        ReportTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
        help_text="Để trống = dùng bộ xuất Excel cũ (tương thích ngược).",
    )
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default=STATUS_PROCESSING
    )
    parameters = models.JSONField(default=dict)
    file = models.FileField(upload_to="reports/", null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="reports",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_report_type_display()} — {self.company.name} ({self.get_status_display()})"


class EmployeeExamReport(BaseModel):
    """Per‑employee examination result, generated as HTML and served publicly.

    Each examination can have at most one employee report.  The report is
    rendered using a :class:`ReportTemplate` (typically *Employee Exam
    Report*) and stored as a static HTML file.  A public URL
    ``/kq/{public_id}/`` points to the report; access is gated by a password
    derived from the patient's CCCD and date of birth.
    """

    STATUS_PROCESSING = "processing"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PROCESSING, "Đang xử lý"),
        (STATUS_DONE, "Hoàn thành"),
        (STATUS_FAILED, "Lỗi"),
    ]

    examination = models.ForeignKey(
        "examinations.Examination",
        on_delete=models.CASCADE,
        related_name="employee_reports",
    )
    template = models.ForeignKey(
        ReportTemplate,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    file = models.FileField(
        upload_to="employee_reports/",
        null=True,
        blank=True,
    )
    cache_version = models.IntegerField(
        default=0,
        help_text="Bumped when rendering logic changes, to invalidate cached HTML.",
    )
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=STATUS_PROCESSING,
    )
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_employee_reports",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["examination"],
                name="unique_employee_report_per_exam",
            )
        ]

    def __str__(self) -> str:
        patient = self.examination.patient if self.examination_id else None
        name = patient.full_name if patient else "?"
        return f"{name} — {self.examination.exam_date}"

    @property
    def public_url(self) -> str:
        prefix = settings.FORCE_SCRIPT_NAME or ""
        return f"{prefix}/ket-qua/{self.examination_id}/"

    @property
    def password(self) -> str:
        """Derived from patient CCCD + DOB, computed on the fly."""
        patient = self.examination.patient
        cccd = (patient.cccd or "").strip()
        last4 = cccd[-4:] if len(cccd) >= 4 else ""
        dob_part = patient.dob.strftime("%d%m%Y") if patient.dob else ""
        pw = last4 + dob_part
        return pw or date.today().strftime("%Y%m%d")
