"""
Public result portal — one password-protected URL per examination.

    GET  /ket-qua/{exam_id}/   → password form / auto-create report
    POST /ket-qua/{exam_id}/   → validate → generate (if needed) → show report
"""

from __future__ import annotations

from django.core.files.base import ContentFile
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.crypto import constant_time_compare

from examinations.models import Examination
from reports.models import EmployeeExamReport, ReportTemplate
from reports.report_builder import build_report_dataset
from reports.render import render_report

# Bump this when the report rendering logic changes so cached HTML is invalidated.
_CACHE_VERSION = 4


def public_result_view(
    request: HttpRequest, exam_id: str | None = None
) -> HttpResponse:
    exam = get_object_or_404(
        Examination.objects.select_related("patient__company", "company_exam_package"),
        id=exam_id,
    )
    report = _get_or_create_report(exam)
    patient = exam.patient

    if request.method == "POST":
        password = (request.POST.get("password") or "").strip()
        if not constant_time_compare(password, report.password):
            return render(
                request,
                "reports/public_result.html",
                {
                    "patient_name": patient.full_name,
                    "exam_date": exam.exam_date.strftime("%d/%m/%Y"),
                    "error": "Sai mật khẩu.",
                    "css": BASE_CSS,
                },
            )

        html_content = _generate_if_needed(report, exam)
        return render(
            request,
            "reports/public_report_view.html",
            {
                "patient": patient,
                "exam_date": exam.exam_date.strftime("%d/%m/%Y"),
                "html_result": html_content,
                "css": BASE_CSS,
            },
        )

    return render(
        request,
        "reports/public_result.html",
        {
            "patient_name": patient.full_name,
            "exam_date": exam.exam_date.strftime("%d/%m/%Y"),
            "error": None,
            "css": BASE_CSS,
        },
    )


def _get_or_create_report(exam: Examination) -> EmployeeExamReport:
    """Return existing report or create a new one on the fly."""
    report, _created = EmployeeExamReport.objects.get_or_create(
        examination=exam,
        defaults={
            "template": ReportTemplate.objects.filter(
                name="Employee Exam Report", is_active=True
            ).first(),
            "status": EmployeeExamReport.STATUS_PROCESSING,
        },
    )
    return report


def _generate_if_needed(report: EmployeeExamReport, exam: Examination) -> str:
    """Return the pre-rendered HTML, generating it synchronously if needed."""
    cep = exam.company_exam_package
    if cep is None:
        return "<p>Không thể tạo báo cáo: thiếu thông tin gói khám.</p>"

    template = report.template or ReportTemplate.objects.filter(
        name="Employee Exam Report", is_active=True
    ).first()

    # Return cached HTML only when both the template hasn't changed and the
    # rendering logic (cache_version) hasn't been bumped since the last render.
    if report.status == EmployeeExamReport.STATUS_DONE and report.file:
        stale = report.cache_version != _CACHE_VERSION or (
            template is not None
            and report.updated_at is not None
            and report.updated_at < template.updated_at
        )
        if not stale:
            try:
                return report.file.read().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                pass

    try:
        ds = build_report_dataset(cep, exam_date=str(exam.exam_date))
        patient = next(
            (p for p in ds.patients if p.examination_id == str(exam.id)), None
        )
        if patient is None:
            return "<p>Không có dữ liệu khám.</p>"

        if template is not None:
            ds.patients = [patient]
            html = render_report(template, ds)
            report.template = template
        else:
            html = _render_result_table(patient)

        filename = (
            f"{_slugify(cep.company.name)}_{patient.ma_nv}"
            f"_{exam.exam_date.isoformat()}.html"
        )
        report.file.save(filename, ContentFile(html.encode("utf-8")), save=False)
        report.status = EmployeeExamReport.STATUS_DONE
        report.cache_version = _CACHE_VERSION
        report.error_message = ""
        report.save()
        return html
    except Exception as e:
        report.status = EmployeeExamReport.STATUS_FAILED
        report.error_message = str(e)
        report.save()
        return f"<p>Lỗi tạo báo cáo: {e}</p>"


def _render_result_table(patient) -> str:
    """Render a per-field result table plus conclusion blocks for one patient."""
    from reports.render import render_result_table_html

    table = render_result_table_html(patient)

    conclusion_blocks = []
    if getattr(patient, "tu_van", ""):
        conclusion_blocks.append(
            f'<div class="conclusion-block">'
            f'<h3>Tư vấn</h3><p>{patient.tu_van}</p></div>'
        )
    if getattr(patient, "ket_luan", ""):
        conclusion_blocks.append(
            f'<div class="conclusion-block">'
            f'<h3>Kết luận</h3><p>{patient.ket_luan}</p></div>'
        )
    if getattr(patient, "benh_mac", ""):
        conclusion_blocks.append(
            f'<div class="conclusion-block">'
            f'<h3>Bệnh mắc</h3><p>{patient.benh_mac}</p></div>'
        )

    return table + "".join(conclusion_blocks)


def _slugify(value: str) -> str:
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "_", ascii_only).strip("_") or "report"


BASE_CSS = """
* { box-sizing: border-box; }
body {
  font-family: "DejaVu Sans", Arial, sans-serif;
  font-size: 10pt; color: #111;
  max-width: 760px; margin: 20px auto; padding: 0 12px;
}
h1 { font-size: 14pt; text-align: center; margin-bottom: 8px; }
.login-box {
  background: #f5f5f5; border: 1px solid #ddd;
  padding: 16px; border-radius: 6px; max-width: 400px; margin: 24px auto;
}
.login-box label { display: block; margin: 8px 0 4px; font-weight: 600; }
.login-box input[type=password] {
  width: 100%; padding: 6px 8px; font: inherit; border: 1px solid #bbb; border-radius: 3px;
}
.login-box button {
  margin-top: 12px; width: 100%; padding: 8px;
  font: inherit; font-weight: 600; background: #417690; color: #fff;
  border: none; border-radius: 4px; cursor: pointer;
}
.login-box button:hover { background: #2e5366; }
.error { color: #b00; font-weight: 600; text-align: center; margin-top: 8px; }
.info-box {
  background: #eaf4e6; border: 1px solid #a2cba0;
  padding: 10px 14px; border-radius: 4px; margin-bottom: 12px;
}
.info-box p { margin: 4px 0; }
table.report-table { width: 100%; border-collapse: collapse; margin: 8px 0; }
table.report-table th, table.report-table td {
  border: 0.4pt solid #888; padding: 4px 6px; text-align: left;
}
table.report-table th { background: #d9ead3; font-weight: bold; }
td.abnormal { color: #c00; font-weight: bold; }
tr.dept-header td {
  background: #eef4ec; font-weight: bold; color: #1b5e20;
}
.conclusion-block { margin-top: 12px; }
.conclusion-block h3 {
  font-size: 11pt; margin: 8px 0 2px; color: #1b5e20;
}
.conclusion-block p { margin: 2px 0; white-space: pre-line; }
.result-panel { margin-top: 16px; }
"""