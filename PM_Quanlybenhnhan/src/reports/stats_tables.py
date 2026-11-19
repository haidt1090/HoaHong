"""HTML fragments for the official company-summary report."""

from __future__ import annotations

from html import escape
from typing import Any

from reports.charts import bar_chart_svg, pie_chart_svg
from reports.stats import CompanyStats, GroupStat


def _num(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def render_gender_table(stats: CompanyStats) -> str:
    return (
        '<table class="report-table stats-overview">'
        "<thead><tr><th>Nội dung</th><th>Tổng số</th><th>Tỷ lệ (%)</th></tr></thead><tbody>"
        f"<tr><td>CBCNV đăng ký khám</td><td>{stats.total}</td><td>100</td></tr>"
        f"<tr><td>CBCNV Nam</td><td>{stats.male}</td><td>{_num(stats.male_pct)}</td></tr>"
        f"<tr><td>CBCNV Nữ</td><td>{stats.female}</td><td>{_num(stats.female_pct)}</td></tr>"
        "</tbody></table>"
    )


def render_classification_table(stats: CompanyStats) -> str:
    if not stats.classifications:
        return '<p class="empty">Chưa có phân loại sức khỏe.</p>'
    rows = []
    for row in stats.classifications:
        rows.append(
            "<tr>"
            f"<td>{escape(row.label)}</td>"
            f"<td>{row.male}</td><td>{row.female}</td>"
            f"<td>{row.count}</td><td>{_num(row.pct)}</td>"
            "</tr>"
        )
    return (
        '<table class="report-table stats-classification">'
        "<thead><tr>"
        "<th>Phân loại sức khỏe</th><th>Nam</th><th>Nữ</th>"
        "<th>Tổng</th><th>Tỷ lệ theo phân loại sức khỏe(%)</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_group_overview_table(stats: CompanyStats) -> str:
    if not stats.groups:
        return '<p class="empty">Chưa có khoa nào trong gói khám.</p>'
    rows = []
    for idx, group in enumerate(stats.groups, 1):
        rows.append(
            "<tr>"
            f"<td>{idx}</td><td>{escape(group.name)}</td>"
            f"<td>{group.normal}</td><td>{group.abnormal}</td>"
            f"<td>{_num(group.pct_normal)}</td><td>{_num(group.pct_abnormal)}</td>"
            "</tr>"
        )
    return (
        '<table class="report-table stats-groups">'
        "<thead><tr>"
        "<th>STT</th><th>Khoa/Nhóm</th>"
        "<th>SL bình thường</th><th>SL bất thường</th>"
        "<th>Tỷ lệ bình thường (%)</th><th>Tỷ lệ bất thường (%)</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_dept_summary(group: GroupStat | None) -> str:
    if group is None:
        return '<p class="empty">Không có số liệu khoa.</p>'
    name = escape(group.name)
    return (
        '<table class="report-table stats-dept-summary">'
        "<thead><tr><th>Khoa</th><th>Số lượng</th><th>Tỷ lệ (%)</th></tr></thead><tbody>"
        f"<tr><td>Tổng số người khám {name} {group.normal_caption}"
        f"</td><td>{group.normal}</td><td>{_num(group.pct_normal)}</td></tr>"
        f"<tr><td>Tổng số người khám {name} {group.abnormal_caption}"
        f"</td><td>{group.abnormal}</td><td>{_num(group.pct_abnormal)}</td></tr>"
        "</tbody></table>"
    )


def render_dept_disease_table(group: GroupStat | None) -> str:
    if group is None or not group.diseases:
        return ""
    rows = []
    for idx, disease in enumerate(group.diseases, 1):
        rows.append(
            "<tr>"
            f"<td>{idx}</td><td class='name'>{escape(disease.name)}</td>"
            f"<td>{disease.count}</td><td>{_num(disease.pct)}</td>"
            "</tr>"
        )
    return (
        '<table class="report-table stats-diseases">'
        "<thead><tr><th>STT</th><th>Chỉ số</th><th>Số lượng</th><th>Tỷ lệ (%)</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_classification_chart(stats: CompanyStats) -> str:
    items = [(row.label, row.pct) for row in stats.classifications]
    return pie_chart_svg(
        items, "Biểu đồ thể hiện tỉ lệ phân loại sức khỏe CBNV (đơn vị %)"
    )


def render_group_overview_chart(stats: CompanyStats) -> str:
    items = [(group.name, group.pct_abnormal) for group in stats.groups]
    return bar_chart_svg(
        items, "Biểu đồ thể hiện tỷ lệ theo từng nhóm bệnh (đơn vị: %)"
    )


def render_dept_chart(group: GroupStat | None, chart_type: str = "pie") -> str:
    if group is None or not group.diseases:
        return ""
    items = [(d.name, d.pct) for d in group.diseases]
    title = f"Biểu đồ thể hiện tỉ lệ bệnh lý {group.name} (đơn vị %)"
    if chart_type == "bar":
        return bar_chart_svg(items, title)
    return pie_chart_svg(items, title)


def render_narrative_bullets(stats: CompanyStats) -> str:
    lines = [
        f"<p>1. Số lượng khám: <b>{stats.total}</b> CBNV.</p>",
        "<p>2. Căn cứ tình hình bệnh tật và thể lực, sức khỏe của CBNV được phân loại như sau:</p>",
        "<ul>",
    ]
    for row in stats.classifications:
        lines.append(
            f"<li>{escape(row.label)}: <b>{row.count}</b> CBNV chiếm "
            f"<b>{_num(row.pct)}%</b></li>"
        )
    lines.append("</ul><p>Mô hình bệnh tật trong khám của CBNV:</p><ul>")
    for group in stats.groups:
        if group.examined == 0:
            continue
        if group.abnormal == 0:
            lines.append(
                f"<li>{escape(group.name)} có <b>{group.examined}</b> CBNV, "
                f"100% {group.normal_caption}.</li>"
            )
        else:
            extra = f" {escape(group.advice)}" if group.advice else ""
            lines.append(
                f"<li>{escape(group.name)}: <b>{group.abnormal}/{group.examined}</b> "
                f"tương đương <b>{_num(group.pct_abnormal)}%</b>.{extra}</li>"
            )
    lines.append("</ul>")
    return "".join(lines)


def stats_from_context(context: dict[str, Any]) -> CompanyStats | None:
    stats = context.get("stats")
    if isinstance(stats, CompanyStats):
        return stats
    dataset = context.get("dataset")
    if dataset is None:
        return None
    from reports.stats import build_company_stats

    return build_company_stats(dataset, (context.get("config") or {}))


def group_from_context(context: dict[str, Any]) -> GroupStat | None:
    group = context.get("group")
    if isinstance(group, GroupStat):
        return group
    stats = stats_from_context(context)
    department = context.get("department")
    if stats is None or department is None:
        return None
    finder = getattr(stats, "group_for", None)
    if callable(finder):
        found = finder(department)
        if found is not None:
            return found
    name = getattr(department, "template_name", None) or getattr(department, "name", "")
    for candidate in stats.groups:
        if candidate.name == name:
            return candidate
    return None
