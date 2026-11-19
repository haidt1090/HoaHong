"""
Custom template tags available inside report templates.

These are registered as **builtins** on the sandboxed engine (see
``reports.render.get_template_engine``), so authors can call them directly in
``body_html`` without ``{% load %}``.

Example::

    {% result_table %}

Renders the per-patient result table for the current ``patient`` in the
context (available in ``department_templates`` body rendering).
"""

from __future__ import annotations

from typing import Any

from django import template
from django.utils.safestring import mark_safe

from reports.result_table import (
    render_company_summary_table,
    render_cost_table,
    render_result_table_html,
)

register = template.Library()


def _render_once(context: dict[str, Any], key: str) -> bool:
    """Return True the first time ``key`` is seen in this report render.

    Report-level tags (company summary, clinical detail, cost) must not be
    repeated when ``department_templates`` loops per patient. ``context["_once"]``
    is a shared mutable dict created in ``build_context`` and copied by
    reference into every per-patient context.
    """
    once = context.get("_once")
    if once is None:
        once = {}
        context["_once"] = once
    if once.get(key):
        return False
    once[key] = True
    return True


@register.simple_tag(takes_context=True)
def result_table(context: dict[str, Any]) -> str:
    """Render the per-field result table for the current patient."""
    patient = context.get("patient")
    html = render_result_table_html(patient) if patient is not None else ""
    return mark_safe(html)


@register.simple_tag(takes_context=True)
def company_summary_table(
    context: dict[str, Any],
    show_normal_range: bool = True,
    highlight_abnormal: bool = True,
) -> str:
    """Render a flat company-summary table (one row per employee).

    Uses the ``dataset`` from the report context. Example::

        {% company_summary_table %}

    Renders at most once per report (safe inside ``department_templates``).
    """
    if not _render_once(context, "company_summary_table"):
        return mark_safe("")
    dataset = context.get("dataset")
    html = (
        render_company_summary_table(
            dataset,
            {
                "show_normal_range": show_normal_range,
                "highlight_abnormal": highlight_abnormal,
            },
        )
        if dataset is not None
        else ""
    )
    return mark_safe(html)


@register.simple_tag(takes_context=True)
def clinical_detail_table(
    context: dict[str, Any],
    highlight_abnormal: bool = True,
    show_normal_range: bool = True,
) -> str:
    """Render the classic clinical detail table (merged R7/R8/R9/R10 header).

    Uses the ``dataset`` from the report context. Example::

        {% clinical_detail_table %}

    Renders at most once per report (safe inside ``department_templates``).
    """
    if not _render_once(context, "clinical_detail_table"):
        return mark_safe("")
    dataset = context.get("dataset")
    if dataset is None:
        return mark_safe("")
    from reports.body_builder import clinical_detail_table as _build

    html = _build(
        dataset,
        {
            "highlight_abnormal": highlight_abnormal,
            "show_normal_range": show_normal_range,
        },
        context,
    )
    return mark_safe(html)


@register.simple_tag(takes_context=True)
def cost_table(context: dict[str, Any]) -> str:
    """Render a per-employee cost table (per-field or package pricing).

    Uses the ``dataset`` from the report context. Example::

        {% cost_table %}

    Renders at most once per report (safe inside ``department_templates``).
    """
    if not _render_once(context, "cost_table"):
        return mark_safe("")
    dataset = context.get("dataset")
    html = render_cost_table(dataset) if dataset is not None else ""
    return mark_safe(html)


def _stats_html(context: dict[str, Any], renderer) -> str:
    from reports.stats_tables import stats_from_context

    stats = stats_from_context(context)
    return renderer(stats) if stats is not None else ""


@register.simple_tag(takes_context=True)
def gender_table(context: dict[str, Any]) -> str:
    """Bảng 1.1 — tổng / nam / nữ."""
    if not _render_once(context, "gender_table"):
        return mark_safe("")
    from reports.stats_tables import render_gender_table

    return mark_safe(_stats_html(context, render_gender_table))


@register.simple_tag(takes_context=True)
def classification_table(context: dict[str, Any]) -> str:
    """Bảng 2.1 — phân loại sức khỏe × nam/nữ."""
    if not _render_once(context, "classification_table"):
        return mark_safe("")
    from reports.stats_tables import render_classification_table

    return mark_safe(_stats_html(context, render_classification_table))


@register.simple_tag(takes_context=True)
def group_overview_table(context: dict[str, Any]) -> str:
    """Bảng 3.0 — tỷ lệ bình thường / bất thường theo từng khoa."""
    if not _render_once(context, "group_overview_table"):
        return mark_safe("")
    from reports.stats_tables import render_group_overview_table

    return mark_safe(_stats_html(context, render_group_overview_table))


@register.simple_tag(takes_context=True)
def classification_chart(context: dict[str, Any]) -> str:
    if not _render_once(context, "classification_chart"):
        return mark_safe("")
    from reports.stats_tables import render_classification_chart

    return mark_safe(_stats_html(context, render_classification_chart))


@register.simple_tag(takes_context=True)
def group_overview_chart(context: dict[str, Any]) -> str:
    if not _render_once(context, "group_overview_chart"):
        return mark_safe("")
    from reports.stats_tables import render_group_overview_chart

    return mark_safe(_stats_html(context, render_group_overview_chart))


@register.simple_tag(takes_context=True)
def dept_summary(context: dict[str, Any]) -> str:
    """Mini-bảng BT / bất thường của khoa đang render."""
    from reports.stats_tables import group_from_context, render_dept_summary

    return mark_safe(render_dept_summary(group_from_context(context)))


@register.simple_tag(takes_context=True)
def dept_disease_table(context: dict[str, Any]) -> str:
    """Bảng 3.n — breakdown bệnh trong khoa. Rỗng nếu không có bệnh."""
    from reports.stats_tables import group_from_context, render_dept_disease_table

    return mark_safe(render_dept_disease_table(group_from_context(context)))


@register.simple_tag(takes_context=True)
def dept_chart(context: dict[str, Any], type: str = "pie") -> str:
    from reports.stats_tables import group_from_context, render_dept_chart

    return mark_safe(render_dept_chart(group_from_context(context), chart_type=type))


@register.simple_tag(takes_context=True)
def narrative_bullets(context: dict[str, Any]) -> str:
    """Đoạn nhận xét: phân loại + một bullet / khoa."""
    if not _render_once(context, "narrative_bullets"):
        return mark_safe("")
    from reports.stats_tables import render_narrative_bullets

    return mark_safe(_stats_html(context, render_narrative_bullets))
