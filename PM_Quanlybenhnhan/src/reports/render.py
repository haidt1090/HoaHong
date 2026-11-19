"""
Dynamic report render engine (Sprint 9a).

Pipeline::

    dataset ──► build_context() ──► {clinic, company, patients, ...}
                     │
                     └─► render body (BodyBuilder / sub-templates)
                                 │
                                 └─► wrap in a full HTML document

Excel letterhead (header/footer) is supplied as uploaded ``.xlsx`` files and
merged in ``reports.tasks`` / ``reports.xlsx_letterhead`` — not via HTML.

Author-supplied templates (``body_html``, department ``body_html``) are
compiled with a restricted Django ``Engine`` — no ``{% include %}``,
``{% extends %}``, ``{% load %}`` or ``{% debug %}`` — so a template author
cannot read arbitrary files from disk or pull in unlisted tag libraries.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from functools import lru_cache
from typing import Any

from django.conf import settings
from django.template import Context, Engine, TemplateSyntaxError
from django.utils import timezone

from reports.report_builder import PatientRecord, ReportDataset
from reports.result_table import render_result_table_html

logger = logging.getLogger(__name__)


class TemplateRenderError(RuntimeError):
    """Raised when an author-supplied template fails to compile or render."""


# ---------------------------------------------------------------------------
# Restricted template engine
# ---------------------------------------------------------------------------

#: Tags removed from the sandboxed engine. ``include``/``extends``/``ssi`` can
#: read files off disk; ``load`` can pull in arbitrary registered libraries;
#: ``debug`` dumps the whole settings object into the output.
BLOCKED_TAGS = ("include", "extends", "ssi", "load", "debug")


class _RestrictedLibrary:
    """
    Read-only view over a template ``Library`` with some tags hidden.

    Django's ``import_library`` returns the module-level ``register`` singleton
    (e.g. ``django.template.defaulttags.register``), which every engine in the
    process shares — including the one Django admin renders with. Mutating
    ``library.tags`` therefore removes those tags globally and breaks unrelated
    templates. This wrapper leaves the shared Library untouched and only
    filters what the sandboxed engine can see.
    """

    def __init__(self, library: Any, blocked: tuple[str, ...]) -> None:
        self._library = library
        self.filters = library.filters
        self.tags = {k: v for k, v in library.tags.items() if k not in blocked}

    def __getattr__(self, item: str) -> Any:
        return getattr(self._library, item)


class RestrictedEngine(Engine):
    """Engine whose builtin tag libraries have the unsafe tags filtered out."""

    def get_template_builtins(self, builtins: list[str]) -> list[Any]:
        return [
            _RestrictedLibrary(library, BLOCKED_TAGS)
            for library in super().get_template_builtins(builtins)
        ]


@lru_cache(maxsize=1)
def get_template_engine() -> Engine:
    """A Django Engine with file-reading and library-loading tags removed.

    ``reports.report_tags`` is registered as a builtin library so authors can
    call ``{% result_table %}`` and friends without ``{% load %}``.
    """
    return RestrictedEngine(
        dirs=[],
        app_dirs=False,
        autoescape=True,
        libraries={},
        builtins=[
            "django.template.defaultfilters",
            "django.template.defaulttags",
            "reports.report_tags",
        ],
    )


def render_fragment(
    source: str, context: dict[str, Any], label: str = "template"
) -> str:
    """Compile and render one author-supplied template fragment."""
    if not source or not source.strip():
        return ""
    engine = get_template_engine()
    try:
        template = engine.from_string(source)
    except TemplateSyntaxError as exc:
        raise TemplateRenderError(f"Lỗi cú pháp trong {label}: {exc}") from exc
    try:
        return template.render(Context(context, autoescape=True))
    except Exception as exc:
        raise TemplateRenderError(f"Lỗi khi render {label}: {exc}") from exc


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------


def get_clinic_info() -> dict[str, str]:
    """Clinic identity used by ``{{ clinic_name }}`` & friends."""
    info = getattr(settings, "CLINIC_INFO", {}) or {}
    return {
        "clinic_name": info.get("name", ""),
        "clinic_address": info.get("address", ""),
        "clinic_phone": info.get("phone", ""),
        "clinic_email": info.get("email", ""),
        "clinic_website": info.get("website", ""),
    }


def build_context(
    dataset: ReportDataset,
    template: Any = None,
    report: Any = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build the shared context available to every template fragment.

    See ``reports.shortcodes.REPORT_VARIABLES`` for the documented surface.
    """
    company = dataset.company
    package = dataset.exam_package
    today = timezone.localdate()

    context: dict[str, Any] = {
        # clinic
        **get_clinic_info(),
        "logo_url": _absolute_media_url(template.logo_url if template else ""),
        # company
        "company": company,
        "company_name": company.name if company else "",
        "company_code": company.code if company else "",
        "company_address": company.address if company else "",
        # package
        "exam_package": package,
        "exam_package_name": package.name if package else "",
        "exam_type": package.get_exam_type_display() if package else "",
        # dates
        "exam_date": dataset.exam_date or "",
        "report_date": today.strftime("%d/%m/%Y"),
        "today": today,
        "day": today.day,
        "month": today.month,
        "year": today.year,
        # data
        "patients": dataset.patients,
        "departments": dataset.departments,
        "total_employees": dataset.total_employees,
        "dataset": dataset,
        # meta
        "report": report,
        "template": template,
        "config": (template.body_config if template else {}) or {},
        # Shared across per-patient copies (same dict object) so report-level
        # tags like {% company_summary_table %} can render only once.
        "_once": {},
    }
    from reports.stats import build_company_stats

    context["stats"] = build_company_stats(dataset, context["config"])
    if extra:
        context.update(extra)
    return context


def build_department_context(
    patient: PatientRecord,
    department: Any,
    base_context: dict[str, Any],
    item_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Context for a ``DepartmentReportTemplate.body_html``.

    Adds ``department``, ``fields`` and ``patient`` on top of the report-level
    context so a department template can render standalone.
    """
    context = dict(base_context)
    context.update(
        {
            "patient": patient,
            "department": department,
            "fields": department.fields if department else [],
            "abnormal_fields": department.abnormal_fields if department else [],
            "has_abnormal": department.has_abnormal if department else False,
            "result_table": render_result_table_html(patient) if patient else "",
            "config": item_config or {},
        }
    )
    return context


def _absolute_media_url(url: str) -> str:
    """
    Make a media URL absolute so WeasyPrint can resolve it off the filesystem.

    WeasyPrint fetches ``/media/...`` relative to ``base_url``; giving it a
    ``file://`` path avoids a network round-trip back into the app.
    """
    if not url:
        return ""
    if url.startswith(("http://", "https://", "file://", "data:")):
        return url
    media_url = str(settings.MEDIA_URL)
    if media_url and url.startswith(media_url):
        relative = url[len(media_url) :]
        path = settings.MEDIA_ROOT / relative
        if path.exists():
            return path.as_uri()
    return url


# ---------------------------------------------------------------------------
# Department sub-template rendering (body_type = "department_templates")
# ---------------------------------------------------------------------------


# Tags that emit a full-report table (all employees). When a department
# template body only uses these, looping per patient would duplicate the table.
_REPORT_LEVEL_TAGS = (
    "company_summary_table",
    "clinical_detail_table",
    "cost_table",
    "gender_table",
    "classification_table",
    "group_overview_table",
    "classification_chart",
    "group_overview_chart",
    "narrative_bullets",
)


def _body_is_report_level_only(body_html: str) -> bool:
    """True when body is a report-wide table tag, not a per-patient booklet."""
    if not body_html or not body_html.strip():
        return False
    has_report_tag = any(tag in body_html for tag in _REPORT_LEVEL_TAGS)
    if not has_report_tag:
        return False
    # Per-patient markers — keep default looping if any are present.
    patient_markers = (
        "result_table",
        "{{ patient",
        "{% for field in fields",
        "for field in abnormal_fields",
    )
    return not any(m in body_html for m in patient_markers)


def _matching_specs(dataset: ReportDataset, item) -> list:
    """Package slots this item should render in per-department mode."""
    specs = list(dataset.departments)
    dept_id = item.resolved_department_id
    if item.exam_template_id:
        specs = [s for s in specs if s.template_id == str(item.exam_template_id)]
    elif dept_id is not None:
        specs = [s for s in specs if s.id == str(dept_id)]
    return specs


def _render_per_department(
    dataset: ReportDataset,
    items: list,
    context: dict[str, Any],
    skip_empty: bool,
) -> str:
    """Render global items once; iterate package slots for department items."""
    stats = context.get("stats")
    out: list[str] = []
    for item in items:
        item_cfg = item.department_template.config or {}
        iterates = bool(item_cfg.get("iterate_departments"))
        if not iterates:
            body = render_fragment(
                item.department_template.body_html,
                {**context, "config": item_cfg},
                label=f"template khoa '{item.department_template.name}'",
            )
            if body and body.strip():
                css = ' class="page-break"' if item.page_break_before else ""
                out.append(f"<section{css}>{body}</section>")
            continue

        for index, spec in enumerate(_matching_specs(dataset, item), start=1):
            group = stats.group_for(spec) if stats is not None else None
            if skip_empty and group is not None and group.examined == 0:
                continue
            body = render_fragment(
                item.department_template.body_html,
                {
                    **context,
                    "department": spec,
                    "group": group,
                    "group_index": index,
                    "config": item_cfg,
                },
                label=f"template khoa '{item.department_template.name}'",
            )
            if not body or not body.strip():
                continue
            css = ' class="page-break"' if item.page_break_before else ""
            out.append(f"<section{css}>{body}</section>")

    return "".join(out) if out else '<p class="empty">Không có dữ liệu.</p>'


def render_department_items(
    dataset: ReportDataset,
    config: dict[str, Any],
    context: dict[str, Any],
) -> str:
    """
    Render every ``ReportTemplateItem`` of the composite template.

    config:
        per_patient   (bool, default True) — repeat the item list per employee.
                      When omitted and every item body is report-level-only
                      (e.g. ``{% company_summary_table %}``), defaults to False
                      so the full company table is not duplicated N times.
        page_break_between_patients (bool, default True)
        skip_empty    (bool, default False) — omit departments with no data
        per_department (bool) — render items with ``iterate_departments``
                      once per package slot (not per patient). Inferred when
                      per_patient is False and any item sets that flag.
    """
    template = context.get("template")
    if template is None:
        return '<p class="empty">Chưa gắn template khoa nào.</p>'

    items = list(
        template.items.select_related(
            "department_template", "department", "department_template__department"
        ).order_by("order")
    )
    if not items:
        return '<p class="empty">Chưa gắn template khoa nào.</p>'

    if "per_patient" in config:
        per_patient = bool(config["per_patient"])
    elif items and all(
        _body_is_report_level_only(item.department_template.body_html) for item in items
    ):
        per_patient = False
    else:
        per_patient = True
    page_break = config.get("page_break_between_patients", True)
    skip_empty = config.get("skip_empty", False)
    if "per_department" in config:
        per_department = bool(config["per_department"])
    else:
        per_department = (not per_patient) and any(
            (item.department_template.config or {}).get("iterate_departments")
            for item in items
        )

    def _select(patient, item):
        """Department results this item should render for one patient."""
        dept_id = item.resolved_department_id
        if dept_id is None:
            cfg = item.department_template.config or {}
            if cfg.get("iterate_departments"):
                return patient.departments or [None]
            return [None]
        matches = patient.departments_for(str(dept_id))
        if item.exam_template_id:
            matches = [
                d for d in matches if d.template_id == str(item.exam_template_id)
            ]
        return matches

    out: list[str] = []

    if per_department:
        return _render_per_department(dataset, items, context, skip_empty)

    if not per_patient:
        # Render each item once; the author iterates {{ patients }} themselves.
        for item in items:
            body = render_fragment(
                item.department_template.body_html,
                {
                    **context,
                    "config": item.department_template.config or {},
                },
                label=f"template khoa '{item.department_template.name}'",
            )
            if not body or not body.strip():
                continue
            css = ' class="page-break"' if item.page_break_before else ""
            out.append(f"<section{css}>{body}</section>")
        return "".join(out) if out else '<p class="empty">Không có dữ liệu.</p>'

    for index, patient in enumerate(dataset.patients):
        blocks: list[str] = []
        for item in items:
            departments = _select(patient, item)
            if not departments:
                if skip_empty:
                    continue
                departments = [None]

            for department in departments:
                if (
                    skip_empty
                    and department is not None
                    and not department.filled_fields
                ):
                    continue
                dept_context = build_department_context(
                    patient,
                    department,
                    context,
                    item.department_template.config or {},
                )
                body = render_fragment(
                    item.department_template.body_html,
                    dept_context,
                    label=f"template khoa '{item.department_template.name}'",
                )
                if not body or not body.strip():
                    continue
                css = ' class="page-break"' if item.page_break_before else ""
                blocks.append(f"<section{css}>{body}</section>")

        if not blocks:
            continue
        break_css = ' class="page-break"' if page_break and index > 0 else ""
        out.append(
            f'<div{break_css} data-patient="{patient.stt}">'
            + "".join(blocks)
            + "</div>"
        )

    if not out:
        return '<p class="empty">Không có dữ liệu.</p>'
    return "".join(out)


# ---------------------------------------------------------------------------
# Full document assembly
# ---------------------------------------------------------------------------

# NOTE: uses a ``__PAGE_SIZE__`` placeholder rather than %-formatting or
# str.format, because the CSS body is full of literal ``%`` (widths) and ``{}``
# (rule blocks) that both of those would try to interpret.
BASE_CSS = """
@page {
  size: __PAGE_SIZE__;
  margin: 10mm 8mm 12mm 8mm;
  @bottom-right { content: "Trang " counter(page) "/" counter(pages); font-size: 8pt; color: #666; }
}
* { box-sizing: border-box; }
body {
  font-family: "DejaVu Sans", "Noto Sans", "Liberation Sans", Arial, sans-serif;
  font-size: 9pt; color: #111; margin: 0;
}
h1, h2, h3 { margin: 0 0 4mm 0; }
.report-header { margin-bottom: 4mm; }
.report-footer { margin-top: 6mm; }
.page-break { page-break-before: always; }
table.report-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
table.report-table th, table.report-table td {
  border: 0.4pt solid #444; padding: 1mm 1.2mm; vertical-align: middle;
  word-wrap: break-word; overflow-wrap: break-word;
}
table.report-table thead th {
  background: #d9ead3; font-weight: bold; text-align: center; font-size: 7.5pt;
}
table.report-table thead { display: table-header-group; }
table.report-table tr { page-break-inside: avoid; }
table.report-table td { font-size: 8pt; text-align: center; }
table.report-table td.name { text-align: left; white-space: nowrap; }
table.report-table .normal-range-row th {
  font-style: italic; font-weight: normal; color: #666; font-size: 7pt;
}
table.report-table .unit { font-weight: normal; font-size: 7pt; color: #555; }
td.abnormal { color: #c00; font-weight: bold; }
tr.dept-header td { background: #eef4ec; font-weight: bold; color: #1b5e20; }
tr.total td, tr.total th { font-weight: bold; background: #f2f2f2; }
.summary-letter p { margin: 1.5mm 0; text-align: justify; }
.summary-letter .title { text-align: center; font-weight: bold; font-size: 12pt; text-transform: uppercase; }
.summary-letter .company { text-align: center; font-weight: bold; font-size: 11pt; margin: 2mm 0 4mm; }
.summary-split {
  display: flex; gap: 6mm; align-items: flex-start; flex-wrap: wrap;
  page-break-inside: avoid; margin: 3mm 0;
}
.summary-split-main { flex: 1 1 55%; min-width: 70mm; }
.summary-split-chart { flex: 1 1 38%; min-width: 55mm; }
.summary-split-chart .chart-caption {
  font-weight: bold; font-size: 9pt; margin: 0 0 2mm; text-align: center;
}
.report-row {
  display: grid; grid-template-columns: repeat(15, minmax(0, 1fr));
  gap: 1mm; align-items: start; width: 100%; page-break-inside: avoid;
}
.report-row > [data-column="1"] { grid-column-start: 1; }
.report-row > [data-column="2"] { grid-column-start: 2; }
.report-row > [data-column="3"] { grid-column-start: 3; }
.report-row > [data-column="4"] { grid-column-start: 4; }
.report-row > [data-column="5"] { grid-column-start: 5; }
.report-row > [data-column="6"] { grid-column-start: 6; }
.report-row > [data-column="7"] { grid-column-start: 7; }
.report-row > [data-column="8"] { grid-column-start: 8; }
.report-row > [data-column="9"] { grid-column-start: 9; }
.report-row > [data-column="10"] { grid-column-start: 10; }
.report-row > [data-column="11"] { grid-column-start: 11; }
.report-row > [data-column="12"] { grid-column-start: 12; }
.report-row > [data-column="13"] { grid-column-start: 13; }
.report-row > [data-column="14"] { grid-column-start: 14; }
.report-row > [data-column="15"] { grid-column-start: 15; }
.report-row > [data-width="1"] { grid-column-end: span 1; }
.report-row > [data-width="2"] { grid-column-end: span 2; }
.report-row > [data-width="3"] { grid-column-end: span 3; }
.report-row > [data-width="4"] { grid-column-end: span 4; }
.report-row > [data-width="5"] { grid-column-end: span 5; }
.report-row > [data-width="6"] { grid-column-end: span 6; }
.report-row > [data-width="7"] { grid-column-end: span 7; }
.report-row > [data-width="8"] { grid-column-end: span 8; }
.report-row > [data-width="9"] { grid-column-end: span 9; }
.report-row > [data-width="10"] { grid-column-end: span 10; }
.report-row > [data-width="11"] { grid-column-end: span 11; }
.report-row > [data-width="12"] { grid-column-end: span 12; }
.report-row > [data-width="13"] { grid-column-end: span 13; }
.report-row > [data-width="14"] { grid-column-end: span 14; }
.report-row > [data-width="15"] { grid-column-end: span 15; }
figure.report-chart { margin: 3mm 0; page-break-inside: avoid; }
.chart-body { display: flex; align-items: center; gap: 6mm; flex-wrap: wrap; }
.chart-legend { font-size: 8pt; }
.chart-legend-row { margin: 0.8mm 0; }
.chart-swatch { display: inline-block; width: 3mm; height: 3mm; margin-right: 1.5mm; vertical-align: middle; }
.chart-bar-row { display: flex; align-items: center; gap: 2mm; margin: 1mm 0; font-size: 8pt; }
.chart-bar-label { min-width: 40mm; }
.chart-bar { display: inline-block; height: 3.2mm; }
.chart-bar-value { color: #444; }
p.empty { font-style: italic; color: #888; }
.signature-row { display: flex; justify-content: space-between; margin-top: 8mm; }
.signature-box { text-align: center; min-width: 60mm; }
"""


def build_document(
    header: str,
    body: str,
    footer: str,
    page_size: str = "A4 landscape",
    extra_css: str = "",
    title: str = "Báo cáo",
) -> str:
    """Wrap rendered fragments into a standalone HTML document.

    Empty header/footer sections are omitted (Excel letterhead is separate).
    """
    css = BASE_CSS.replace("__PAGE_SIZE__", page_size or "A4 landscape")
    if extra_css:
        css = f"{css}\n/* --- extra_css --- */\n{extra_css}"
    parts = [
        "<!DOCTYPE html>\n",
        '<html lang="vi"><head><meta charset="utf-8">',
        f"<title>{title}</title>",
        f"<style>{css}</style>",
        "</head><body>",
    ]
    if header and header.strip():
        parts.append(f'<div class="report-header">{header}</div>')
    parts.append(f'<main class="report-body">{body}</main>')
    if footer and footer.strip():
        parts.append(f'<div class="report-footer">{footer}</div>')
    parts.append("</body></html>")
    return "".join(parts)


def render_report(
    template: Any,
    dataset: ReportDataset,
    report: Any = None,
    extra_context: dict[str, Any] | None = None,
) -> str:
    """Render a ``ReportTemplate`` against a dataset into a full HTML document."""
    from reports.body_builder import BodyBuilder

    # Safety net for rows that bypassed form/serializer validation (fixtures,
    # shell, pre-existing data): department items only render under the
    # ``department_templates`` body type, so warn instead of dropping silently.
    with suppress(AttributeError):
        orphaned = template.orphaned_item_count()
        if orphaned:
            logger.warning(
                "ReportTemplate %r (body_type=%s) has %d department template(s) "
                "attached that this body_type does not render.",
                template.name,
                template.body_type,
                orphaned,
            )

    context = build_context(
        dataset, template=template, report=report, extra=extra_context
    )

    header = ""
    body = BodyBuilder.render(
        template.body_type,
        dataset,
        config=template.body_config or {},
        context=context,
        body_html=getattr(template, "body_html", "") or "",
    )
    footer = ""

    return build_document(
        header,
        body,
        footer,
        page_size=template.page_size,
        extra_css=template.extra_css or "",
        title=f"{template.name} — {context.get('company_name', '')}".strip(" —"),
    )


def render_to_pdf(html: str, base_url: str | None = None) -> bytes:
    """Convert an HTML document to PDF bytes via WeasyPrint."""
    try:
        from weasyprint import HTML
    except OSError as exc:  # missing pango/cairo system libraries
        raise TemplateRenderError(
            "WeasyPrint chưa cài đủ thư viện hệ thống (libpango/libcairo). "
            f"Chi tiết: {exc}"
        ) from exc

    return HTML(
        string=html,
        base_url=base_url or str(settings.MEDIA_ROOT),
    ).write_pdf()
