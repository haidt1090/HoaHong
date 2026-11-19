"""
Coded body functions for the dynamic report template engine (Sprint 9a).

Each body function receives ``(dataset, config, context)`` and returns an HTML
string. ``BodyBuilder.render`` dispatches on ``ReportTemplate.body_type``.

Adding a new body type:
    1. write ``def _my_body(dataset, config, context) -> str``
    2. register it in ``BodyBuilder.REGISTRY``
    3. add the choice to ``ReportTemplate.BODY_TYPE_CHOICES``
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from collections.abc import Callable
from decimal import Decimal
from html import escape
from typing import Any

from reports.report_builder import ReportData, ReportDataset


class UnknownBodyType(ValueError):
    """Raised when a ReportTemplate references a body_type with no builder."""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _esc(value: Any) -> str:
    if value is None:
        return ""
    return escape(str(value), quote=True)


def _cell_class(is_abnormal: bool, highlight: bool) -> str:
    return ' class="abnormal"' if (is_abnormal and highlight) else ""


def _money(value: Any) -> str:
    try:
        return f"{Decimal(str(value)):,.0f}".replace(",", ".")
    except Exception:
        return str(value or "")


# ---------------------------------------------------------------------------
# body: clinical_detail_table — wide horizontal table, one row per employee
# ---------------------------------------------------------------------------


def clinical_detail_table(
    dataset: ReportDataset, config: dict[str, Any], context: dict[str, Any]
) -> str:
    """
    Horizontal detail table: one row per employee, one column per field.

    Reuses the grouped/merged column layout already produced by
    ``build_clinical_detail_report`` so the HTML matches the Excel export.

    config:
        highlight_abnormal (bool, default True)
        show_normal_range  (bool, default True)
        include_personal   (bool, default True)
        include_conclusion (bool, default True)
    """
    table: ReportData | None = dataset.table
    if table is None or not table.headers.columns:
        return '<p class="empty">Không có dữ liệu.</p>'

    highlight = config.get("highlight_abnormal", True)
    show_range = config.get("show_normal_range", True)
    include_personal = config.get("include_personal", True)
    include_conclusion = config.get("include_conclusion", True)

    conclusion_headers = {"Phân loại sức khỏe", "Bệnh mắc", "Tư vấn", "Kết luận"}
    personal_key_map = {
        "STT": "stt",
        "Số hồ sơ": "so_ho_so",
        "Mã NV": "ma_nv",
        "Họ và tên": "ho_ten",
        "Ngày sinh": "ngay_sinh",
        "Giới tính": "gioi_tinh",
        "Bộ phận": "bo_phan",
        "CCCD": "cccd",
        "Nơi ở hiện tại": "noi_o",
        "Ngày bắt đầu làm việc": "ngay_vao",
        "Phân loại sức khỏe": "phan_loai",
        "Bệnh mắc": "benh_mac",
        "Tư vấn": "tu_van",
        "Kết luận": "ket_luan",
    }

    columns = []
    for col in table.headers.columns:
        if col.field is None:
            if not include_personal and col.header_personal not in conclusion_headers:
                continue
            if not include_conclusion and col.header_personal in conclusion_headers:
                continue
        columns.append(col)

    if not columns:
        return '<p class="empty">Không có cột nào được chọn.</p>'

    # Abnormal bounds keyed by field_key for O(1) lookup while emitting cells.
    bounds = {
        c.field.field_key: (c.field.normal_min, c.field.normal_max)
        for c in columns
        if c.field
    }

    out: list[str] = ['<table class="report-table clinical-detail">']

    # ── Row 1: parent department (R7) ──
    out.append("<thead>")
    out.append("<tr>")
    # Personal columns lead and trail the field columns; they span every
    # header row so the grouped department headers sit above the fields only.
    leading = 0
    for c in columns:
        if c.field is not None:
            break
        leading += 1
    trailing = 0
    for c in reversed(columns):
        if c.field is not None:
            break
        trailing += 1

    header_rows = 3 if show_range else 2
    for c in columns[:leading]:
        out.append(f'<th rowspan="{header_rows + 1}">{_esc(c.header_personal)}</th>')
    field_cols = (
        columns[leading : len(columns) - trailing] if trailing else columns[leading:]
    )
    for c in field_cols:
        if c.field and c.merge_parent:
            label = c.field.parent_name or c.field.department_name
            out.append(f'<th colspan="{c.parent_span}">{_esc(label)}</th>')
    for c in columns[len(columns) - trailing :] if trailing else []:
        out.append(f'<th rowspan="{header_rows + 1}">{_esc(c.header_personal)}</th>')
    out.append("</tr>")

    # ── Row 2: department (R8) ──
    out.append("<tr>")
    for c in field_cols:
        if c.field and c.merge_child:
            out.append(
                f'<th colspan="{c.child_span}">{_esc(c.field.department_name)}</th>'
            )
    out.append("</tr>")

    # ── Row 3: field labels ──
    out.append("<tr>")
    for c in field_cols:
        if c.field:
            label = c.field.label
            if c.field.unit:
                label += f" ({c.field.unit})"
            out.append(f"<th>{_esc(label)}</th>")
    out.append("</tr>")

    # ── Row 4: normal ranges ──
    if show_range:
        out.append('<tr class="normal-range-row">')
        for c in field_cols:
            if c.field:
                out.append(f"<th>{_esc(c.field.normal_range)}</th>")
        out.append("</tr>")
    out.append("</thead>")

    # ── Body ──
    out.append("<tbody>")
    for row in table.rows:
        out.append("<tr>")
        for c in columns:
            if c.field:
                value = row.get(c.field.field_key, "")
                nmin, nmax = bounds.get(c.field.field_key, (None, None))
                abnormal = _is_out_of_range(value, nmin, nmax)
                out.append(f"<td{_cell_class(abnormal, highlight)}>{_esc(value)}</td>")
            else:
                key = personal_key_map.get(c.header_personal or "", "")
                out.append(f"<td>{_esc(row.get(key, ''))}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def _is_out_of_range(value: Any, nmin: float | None, nmax: float | None) -> bool:
    if value in (None, ""):
        return False
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return False
    if nmin is not None and number < nmin:
        return True
    return bool(nmax is not None and number > nmax)


# ---------------------------------------------------------------------------
# body: clinical_detail_blood_test — vertical table, employees as rows
# ---------------------------------------------------------------------------


def clinical_detail_blood_test(
    dataset: ReportDataset, config: dict[str, Any], context: dict[str, Any]
) -> str:
    """
    Blood-test table: one row per employee, one column per selected test field.

    config:
        columns           (list[str]) field keys to show; empty = auto-detect
                          every field whose test_category looks haematological
        department_code   (str) restrict auto-detection to one department code
        test_category     (str) restrict auto-detection to one test_category
        highlight_abnormal(bool, default True)
        show_normal_range (bool, default True)
        show_unit         (bool, default True)
    """
    highlight = config.get("highlight_abnormal", True)
    show_range = config.get("show_normal_range", True)
    show_unit = config.get("show_unit", True)
    wanted: list[str] = list(config.get("columns") or [])
    dept_code = config.get("department_code") or ""
    category = config.get("test_category") or ""

    # Resolve the column set + metadata from the package specs.
    meta: OrderedDict[str, Any] = OrderedDict()
    for spec in dataset.departments:
        if dept_code and spec.code != dept_code:
            continue
        for f in spec.fields:
            if category and f.test_category != category:
                continue
            if wanted and f.field_key not in wanted:
                continue
            if f.field_key not in meta:
                meta[f.field_key] = f

    if wanted:
        # Preserve the caller's explicit ordering.
        meta = OrderedDict((k, meta[k]) for k in wanted if k in meta)

    if not meta:
        return '<p class="empty">Không có chỉ số nào khớp cấu hình.</p>'

    out: list[str] = ['<table class="report-table blood-test">']
    out.append("<thead><tr>")
    out.append('<th rowspan="2">STT</th>')
    out.append('<th rowspan="2">Mã NV</th>')
    out.append('<th rowspan="2">Họ và tên</th>')
    out.append('<th rowspan="2">Năm sinh</th>')
    out.append('<th rowspan="2">Giới</th>')
    for f in meta.values():
        if show_unit and f.unit:
            out.append(
                f"<th>{_esc(f.label)}<br><span class='unit'>({_esc(f.unit)})</span></th>"
            )
        else:
            out.append(f"<th>{_esc(f.label)}</th>")
    out.append("</tr>")
    if show_range:
        out.append('<tr class="normal-range-row">')
        for f in meta.values():
            out.append(f"<th>{_esc(f.normal_range)}</th>")
        out.append("</tr>")
    else:
        # Keep the rowspan=2 header cells valid.
        out.append("<tr></tr>")
    out.append("</thead><tbody>")

    for p in dataset.patients:
        # Build a per-patient lookup that keeps abnormal flags.
        by_key: dict[str, Any] = {}
        for d in p.departments:
            if dept_code and d.code != dept_code:
                continue
            for f in d.fields:
                if f.key in meta and (f.key not in by_key or not f.is_empty):
                    by_key[f.key] = f

        out.append("<tr>")
        out.append(f"<td>{p.stt}</td>")
        out.append(f"<td>{_esc(p.ma_nv)}</td>")
        out.append(f'<td class="name">{_esc(p.ho_ten)}</td>')
        out.append(f"<td>{_esc(p.ngay_sinh)}</td>")
        out.append(f"<td>{_esc(p.gioi_tinh_display)}</td>")
        for key in meta:
            f = by_key.get(key)
            if f is None:
                out.append("<td></td>")
            else:
                out.append(
                    f"<td{_cell_class(f.is_abnormal, highlight)}>{_esc(f.value)}</td>"
                )
        out.append("</tr>")

    out.append("</tbody></table>")
    return "".join(out)


# ---------------------------------------------------------------------------
# body: summary_stats
# ---------------------------------------------------------------------------


def summary_stats(
    dataset: ReportDataset, config: dict[str, Any], context: dict[str, Any]
) -> str:
    """
    Aggregate counts: employees, gender split, health classification, top
    diseases, and per-department abnormal counts.

    config:
        top_diseases (int, default 10)
        show_departments (bool, default True)
    """
    top_n = int(config.get("top_diseases", 10))
    show_departments = config.get("show_departments", True)

    total = dataset.total_employees
    male = sum(1 for p in dataset.patients if p.gioi_tinh == "M")
    female = sum(1 for p in dataset.patients if p.gioi_tinh == "F")

    classification: OrderedDict[str, int] = OrderedDict()
    diseases: dict[str, int] = {}
    for p in dataset.patients:
        label = p.ket_luan or "Chưa phân loại"
        classification[label] = classification.get(label, 0) + 1
        for name in filter(None, (d.strip() for d in p.benh_mac.split(","))):
            diseases[name] = diseases.get(name, 0) + 1

    def pct(n: int) -> str:
        return f"{(n / total * 100):.1f}%" if total else "0.0%"

    out: list[str] = ['<div class="summary-stats">']

    out.append('<table class="report-table stats-overview">')
    out.append("<tbody>")
    out.append(f"<tr><th>Tổng số nhân viên</th><td>{total}</td><td></td></tr>")
    out.append(f"<tr><th>Nam</th><td>{male}</td><td>{pct(male)}</td></tr>")
    out.append(f"<tr><th>Nữ</th><td>{female}</td><td>{pct(female)}</td></tr>")
    out.append("</tbody></table>")

    out.append("<h3>Phân loại sức khỏe</h3>")
    out.append('<table class="report-table stats-classification">')
    out.append(
        "<thead><tr><th>Phân loại</th><th>Số lượng</th><th>Tỷ lệ</th></tr></thead><tbody>"
    )
    for label, count in sorted(classification.items(), key=lambda kv: -kv[1]):
        out.append(
            f"<tr><td>{_esc(label)}</td><td>{count}</td><td>{pct(count)}</td></tr>"
        )
    out.append("</tbody></table>")

    if diseases:
        out.append("<h3>Bệnh thường gặp</h3>")
        out.append('<table class="report-table stats-diseases">')
        out.append(
            "<thead><tr><th>STT</th><th>Tên bệnh</th><th>Số ca</th><th>Tỷ lệ</th></tr></thead><tbody>"
        )
        ranked = sorted(diseases.items(), key=lambda kv: -kv[1])[:top_n]
        for i, (name, count) in enumerate(ranked, 1):
            out.append(
                f"<tr><td>{i}</td><td>{_esc(name)}</td><td>{count}</td>"
                f"<td>{pct(count)}</td></tr>"
            )
        out.append("</tbody></table>")

    if show_departments:
        rows = []
        for spec in dataset.departments:
            abnormal = 0
            examined = 0
            for p in dataset.patients:
                for d in p.departments_for(spec.id):
                    if d.filled_fields:
                        examined += 1
                    abnormal += len(d.abnormal_fields)
            if examined or abnormal:
                rows.append((spec.name, examined, abnormal))
        if rows:
            out.append("<h3>Thống kê theo khoa</h3>")
            out.append('<table class="report-table stats-departments">')
            out.append(
                "<thead><tr><th>Khoa</th><th>Đã khám</th><th>Chỉ số bất thường</th></tr></thead><tbody>"
            )
            for name, examined, abnormal in rows:
                out.append(
                    f"<tr><td>{_esc(name)}</td><td>{examined}</td><td>{abnormal}</td></tr>"
                )
            out.append("</tbody></table>")

    out.append("</div>")
    return "".join(out)


# ---------------------------------------------------------------------------
# body: cost_breakdown
# ---------------------------------------------------------------------------


def cost_breakdown(
    dataset: ReportDataset, config: dict[str, Any], context: dict[str, Any]
) -> str:
    """
    Per-field cost table derived from ``DepartmentField.default_price``.

    config:
        show_per_patient (bool, default False) — add a per-employee total table
    """
    from examinations.models import DepartmentField

    cep = dataset.company_exam_package
    show_per_patient = config.get("show_per_patient", False)

    # Sample/preview datasets carry synthetic non-UUID template ids; skip the
    # price lookup rather than letting the ORM raise on an invalid UUID.
    template_ids = []
    for spec in dataset.departments:
        if not spec.template_id:
            continue
        try:
            uuid.UUID(str(spec.template_id))
        except (ValueError, AttributeError, TypeError):
            continue
        template_ids.append(spec.template_id)

    prices: dict[tuple[str, str], Decimal] = {}
    labels: dict[tuple[str, str], tuple[str, str]] = {}
    if template_ids:
        for f in DepartmentField.objects.filter(
            template_id__in=template_ids
        ).select_related("template__department"):
            key = (str(f.template_id), f.key)
            prices[key] = f.default_price or Decimal(0)
            labels[key] = (f.template.department.name, f.label)

    out: list[str] = ['<div class="cost-breakdown">']

    if cep and cep.pricing_mode == "package_total":
        unit = dataset.exam_package.default_package_price or Decimal(0)
        total = unit * dataset.total_employees
        out.append('<table class="report-table cost-summary"><tbody>')
        out.append(
            f"<tr><th>Gói khám</th><td>{_esc(dataset.exam_package.name)}</td></tr>"
        )
        out.append(f"<tr><th>Đơn giá trọn gói</th><td>{_money(unit)} đ</td></tr>")
        out.append(f"<tr><th>Số nhân viên</th><td>{dataset.total_employees}</td></tr>")
        out.append(
            f'<tr class="total"><th>Tổng cộng</th><td>{_money(total)} đ</td></tr>'
        )
        out.append("</tbody></table>")
        out.append("</div>")
        return "".join(out)

    # per_field pricing: count how many employees actually have each field filled
    counts: dict[tuple[str, str], int] = {}
    per_patient: dict[str, Decimal] = {}
    for p in dataset.patients:
        subtotal = Decimal(0)
        for d in p.departments:
            for f in d.fields:
                if f.is_empty:
                    continue
                key = (d.template_id, f.key)
                if key not in prices:
                    continue
                counts[key] = counts.get(key, 0) + 1
                subtotal += prices[key]
        per_patient[p.ho_ten] = subtotal

    out.append('<table class="report-table cost-detail">')
    out.append(
        "<thead><tr><th>STT</th><th>Khoa</th><th>Chỉ số</th><th>Đơn giá</th>"
        "<th>Số lượt</th><th>Thành tiền</th></tr></thead><tbody>"
    )
    grand = Decimal(0)
    i = 0
    for key, count in sorted(
        counts.items(), key=lambda kv: labels.get(kv[0], ("", ""))
    ):
        price = prices.get(key, Decimal(0))
        if not price:
            continue
        i += 1
        line = price * count
        grand += line
        dept_name, field_label = labels.get(key, ("", key[1]))
        out.append(
            f"<tr><td>{i}</td><td>{_esc(dept_name)}</td><td>{_esc(field_label)}</td>"
            f"<td>{_money(price)}</td><td>{count}</td><td>{_money(line)}</td></tr>"
        )
    out.append(
        f'<tr class="total"><td colspan="5">TỔNG CỘNG</td><td>{_money(grand)} đ</td></tr>'
    )
    out.append("</tbody></table>")

    if show_per_patient:
        out.append("<h3>Chi phí theo nhân viên</h3>")
        out.append('<table class="report-table cost-per-patient">')
        out.append(
            "<thead><tr><th>STT</th><th>Họ và tên</th><th>Thành tiền</th></tr></thead><tbody>"
        )
        for i, (name, amount) in enumerate(per_patient.items(), 1):
            out.append(
                f"<tr><td>{i}</td><td>{_esc(name)}</td><td>{_money(amount)}</td></tr>"
            )
        out.append("</tbody></table>")

    out.append("</div>")
    return "".join(out)


# ---------------------------------------------------------------------------
# body: department_templates — render the composite's sub-templates
# ---------------------------------------------------------------------------


def render_template_items(
    dataset: ReportDataset, config: dict[str, Any], context: dict[str, Any]
) -> str:
    """
    Render each ``ReportTemplateItem`` of the composite template.

    ``config`` supports:
        per_patient (bool, default True) — repeat the whole item list once per
                    employee (a booklet). When False the items render once with
                    the full patient list available as ``{{ patients }}``.
    """
    # Imported lazily: ``reports.render`` imports this module.
    from reports.render import render_department_items

    return render_department_items(dataset, config, context)


class BodyBuilder:
    """Dispatch table mapping ``ReportTemplate.body_type`` → body function.

    When ``body_html`` is provided and non-blank (and ``body_type`` is one of
    the four coded types), the template path is used: Python pre-computes a
    type-specific context and renders ``body_html`` via the sandbox engine.
    Otherwise the original Python fallback runs unchanged.
    """

    REGISTRY: dict[str, Callable[[ReportDataset, dict, dict], str]] = {
        "clinical_detail_table": clinical_detail_table,
        "clinical_detail_blood_test": clinical_detail_blood_test,
        "summary_stats": summary_stats,
        "cost_breakdown": cost_breakdown,
        "department_templates": render_template_items,
    }

    # ------------------------------------------------------------------
    # context builders — one per coded body type
    #
    # Each returns a dict that is merged into the template context so a
    # user-authored ``body_html`` can consume pre-structured data without
    # needing custom template filters.  The data is intentionally flat
    # (lists of dicts, parallel arrays) so that Django's default template
    # language — which cannot look up dict entries by a variable key —
    # can iterate it with plain ``{% for %}`` loops.
    # ------------------------------------------------------------------

    @staticmethod
    def _ctx_clinical_detail_table(
        dataset: ReportDataset, config: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        table = dataset.table
        if table is None or not table.headers.columns:
            return {"d_rows": []}

        highlight = config.get("highlight_abnormal", True)
        show_range = config.get("show_normal_range", True)

        personal_key_map = {
            "STT": "stt",
            "Số hồ sơ": "so_ho_so",
            "Mã NV": "ma_nv",
            "Họ và tên": "ho_ten",
            "Ngày sinh": "ngay_sinh",
            "Giới tính": "gioi_tinh",
            "Bộ phận": "bo_phan",
            "CCCD": "cccd",
            "Nơi ở hiện tại": "noi_o",
            "Ngày bắt đầu làm việc": "ngay_vao",
            "Phân loại sức khỏe": "phan_loai",
            "Bệnh mắc": "benh_mac",
            "Tư vấn": "tu_van",
            "Kết luận": "ket_luan",
        }

        columns = [c for c in table.headers.columns]

        # ── Header structure ──
        leading = 0
        for c in columns:
            if c.field is not None:
                break
            leading += 1
        trailing = 0
        for c in reversed(columns):
            if c.field is not None:
                break
            trailing += 1
        field_cols = (
            columns[leading : len(columns) - trailing]
            if trailing
            else columns[leading:]
        )

        header_rows = 3 if show_range else 2

        # Row 1: parent department names (R7) — one cell per merge_parent start
        r1_cells: list[dict[str, Any]] = [
            {"label": c.header_personal, "span": 1, "rowspan": header_rows + 1}
            for c in columns[:leading]
        ]
        for c in field_cols:
            if c.field and c.merge_parent:
                r1_cells.append(
                    {
                        "label": c.field.parent_name or c.field.department_name,
                        "span": c.parent_span,
                        "rowspan": 1,
                    }
                )
        for c in columns[len(columns) - trailing :] if trailing else []:
            r1_cells.append(
                {"label": c.header_personal, "span": 1, "rowspan": header_rows + 1}
            )

        # Row 2: department names (R8)
        r2_cells: list[dict[str, Any]] = [
            {"label": c.field.department_name, "span": c.child_span, "rowspan": 1}
            for c in field_cols
            if c.field and c.merge_child
        ]

        # Row 3: field labels
        r3_cells: list[dict[str, Any]] = [
            {
                "label": (
                    f"{c.field.label} ({c.field.unit})"
                    if c.field.unit
                    else c.field.label
                ),
                "span": 1,
                "rowspan": 1,
            }
            for c in field_cols
            if c.field
        ]

        # Row 4: normal ranges
        r4_cells: list[dict[str, Any]] = [
            {"label": c.field.normal_range, "span": 1, "rowspan": 1}
            for c in field_cols
            if c.field
        ]

        header = {"r1": r1_cells, "r2": r2_cells, "r3": r3_cells}
        if show_range:
            header["r4"] = r4_cells

        # ── Body rows ──
        d_rows: list[dict[str, Any]] = []
        for row in table.rows:
            cells: list[dict[str, Any]] = []
            for c in columns:
                if c.field:
                    value = row.get(c.field.field_key, "")
                    abnormal = _is_out_of_range(
                        value, c.field.normal_min, c.field.normal_max
                    )
                    cells.append({"text": value, "abnormal": abnormal and highlight})
                else:
                    key = personal_key_map.get(c.header_personal or "", "")
                    cells.append({"text": row.get(key, ""), "abnormal": False})
            d_rows.append({"cells": cells})

        field_label_list = [c["label"] for c in r3_cells]
        return {
            "d_header": header,
            "d_header_rows": header_rows,
            "d_rows": d_rows,
            "d_field_count": len(field_label_list),
            "d_show_range": show_range,
            "d_highlight": highlight,
        }

    @staticmethod
    def _ctx_blood_test(
        dataset: ReportDataset, config: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        highlight = config.get("highlight_abnormal", True)
        show_range = config.get("show_normal_range", True)
        show_unit = config.get("show_unit", True)
        wanted: list[str] = list(config.get("columns") or [])
        dept_code = config.get("department_code") or ""
        category = config.get("test_category") or ""

        meta: OrderedDict[str, Any] = OrderedDict()
        for spec in dataset.departments:
            if dept_code and spec.code != dept_code:
                continue
            for f in spec.fields:
                if category and f.test_category != category:
                    continue
                if wanted and f.field_key not in wanted:
                    continue
                if f.field_key not in meta:
                    meta[f.field_key] = f
        if wanted:
            meta = OrderedDict((k, meta[k]) for k in wanted if k in meta)
        if not meta:
            return {"d_rows": [], "d_columns": []}

        blood_cols: list[dict[str, Any]] = [
            {
                "key": f.field_key,
                "label": f.label,
                "unit": f.unit if show_unit else "",
                "normal_range": f.normal_range if show_range else "",
            }
            for f in meta.values()
        ]

        d_rows: list[dict[str, Any]] = []
        for p in dataset.patients:
            by_key: dict[str, Any] = {}
            for d in p.departments:
                if dept_code and d.code != dept_code:
                    continue
                for f in d.fields:
                    if f.key in meta and (f.key not in by_key or not f.is_empty):
                        by_key[f.key] = f

            cells: list[dict[str, Any]] = []
            for key in meta:
                f = by_key.get(key)
                if f is None:
                    cells.append({"text": "", "abnormal": False})
                else:
                    cells.append(
                        {"text": f.value, "abnormal": f.is_abnormal and highlight}
                    )
            d_rows.append(
                {
                    "stt": p.stt,
                    "ma_nv": p.ma_nv,
                    "ho_ten": p.ho_ten,
                    "ngay_sinh": p.ngay_sinh,
                    "gioi_tinh": p.gioi_tinh_display,
                    "cells": cells,
                }
            )

        return {
            "d_columns": blood_cols,
            "d_rows": d_rows,
            "d_show_range": show_range,
            "d_highlight": highlight,
        }

    @staticmethod
    def _ctx_summary_stats(
        dataset: ReportDataset, config: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        top_n = int(config.get("top_diseases", 10))
        show_departments = config.get("show_departments", True)

        total = dataset.total_employees
        male = sum(1 for p in dataset.patients if p.gioi_tinh == "M")
        female = sum(1 for p in dataset.patients if p.gioi_tinh == "F")

        classification: dict[str, int] = {}
        diseases: dict[str, int] = {}
        for p in dataset.patients:
            label = p.ket_luan or "Chưa phân loại"
            classification[label] = classification.get(label, 0) + 1
            for name in filter(None, (d.strip() for d in p.benh_mac.split(","))):
                diseases[name] = diseases.get(name, 0) + 1

        def _pct(cnt: int) -> str:
            return f"{(cnt / total * 100):.1f}" if total else "0.0"

        ctx: dict[str, Any] = {
            "s_total": total,
            "s_male": male,
            "s_female": female,
            "s_male_pct": _pct(male),
            "s_female_pct": _pct(female),
            "s_classifications": sorted(
                (
                    {"label": lbl, "count": cnt, "pct": _pct(cnt)}
                    for lbl, cnt in classification.items()
                ),
                key=lambda x: -x["count"],
            ),
            "s_diseases": [
                {"name": name, "count": cnt, "pct": _pct(cnt)}
                for name, cnt in sorted(diseases.items(), key=lambda kv: -kv[1])[:top_n]
            ],
        }

        if show_departments:
            dept_stats: list[dict[str, Any]] = []
            for spec in dataset.departments:
                abnormal = 0
                examined = 0
                for p in dataset.patients:
                    for d in p.departments_for(spec.id):
                        if d.filled_fields:
                            examined += 1
                        abnormal += len(d.abnormal_fields)
                if examined or abnormal:
                    dept_stats.append(
                        {"name": spec.name, "examined": examined, "abnormal": abnormal}
                    )
            ctx["s_departments"] = dept_stats

        return ctx

    @staticmethod
    def _ctx_cost_breakdown(
        dataset: ReportDataset, config: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        from examinations.models import DepartmentField

        cep = dataset.company_exam_package
        show_per_patient = config.get("show_per_patient", False)

        template_ids = []
        for spec in dataset.departments:
            if not spec.template_id:
                continue
            try:
                uuid.UUID(str(spec.template_id))
            except (ValueError, AttributeError, TypeError):
                continue
            template_ids.append(spec.template_id)

        prices: dict[tuple[str, str], Decimal] = {}
        labels: dict[tuple[str, str], tuple[str, str]] = {}
        if template_ids:
            for f in DepartmentField.objects.filter(
                template_id__in=template_ids
            ).select_related("template__department"):
                key = (str(f.template_id), f.key)
                prices[key] = f.default_price or Decimal(0)
                labels[key] = (f.template.department.name, f.label)

        if cep and cep.pricing_mode == "package_total":
            unit = dataset.exam_package.default_package_price or Decimal(0)
            return {
                "c_mode": "package_total",
                "c_package_name": dataset.exam_package.name,
                "c_unit_price": _money(unit),
                "c_total_employees": dataset.total_employees,
                "c_total": _money(unit * dataset.total_employees),
            }

        counts: dict[tuple[str, str], int] = {}
        per_patient_totals: list[dict[str, Any]] = []
        for p in dataset.patients:
            subtotal = Decimal(0)
            for d in p.departments:
                for f in d.fields:
                    if f.is_empty:
                        continue
                    key = (d.template_id, f.key)
                    if key not in prices:
                        continue
                    counts[key] = counts.get(key, 0) + 1
                    subtotal += prices[key]
            per_patient_totals.append({"name": p.ho_ten, "amount": subtotal})

        lines: list[dict[str, Any]] = []
        grand = Decimal(0)
        for key, count in sorted(
            counts.items(), key=lambda kv: labels.get(kv[0], ("", ""))
        ):
            price = prices.get(key, Decimal(0))
            if not price:
                continue
            line = price * count
            dept_name, field_label = labels.get(key, ("", key[1]))
            lines.append(
                {
                    "dept": dept_name,
                    "field": field_label,
                    "unit_price": _money(price),
                    "count": count,
                    "line_total": _money(line),
                }
            )
            grand += line

        result: dict[str, Any] = {
            "c_mode": "per_field",
            "c_lines": lines,
            "c_grand_total": _money(grand),
        }
        if show_per_patient:
            result["c_per_patient"] = [
                {"name": name, "amount": _money(amount)}
                for name, amount in per_patient_totals
            ]
        return result

    _CONTEXT_BUILDERS: dict[
        str, Callable[[ReportDataset, dict, dict], dict[str, Any]]
    ] = {
        "clinical_detail_table": _ctx_clinical_detail_table,
        "clinical_detail_blood_test": _ctx_blood_test,
        "summary_stats": _ctx_summary_stats,
        "cost_breakdown": _ctx_cost_breakdown,
    }

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    @classmethod
    def render(
        cls,
        body_type: str,
        dataset: ReportDataset,
        config: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        body_html: str = "",
    ) -> str:
        config = config or {}
        context = context or {}

        # Only the four coded body types support a user-authored template
        # override.  ``department_templates`` uses per-department sub-templates
        # (DepartmentReportTemplate.body_html) and has its own rendering path;
        # ``body_html`` is ignored there.
        if body_type != "department_templates" and body_html and body_html.strip():
            builder = cls._CONTEXT_BUILDERS.get(body_type)
            if builder is not None:
                enriched = dict(context)
                enriched["config"] = dict(config)
                enriched.update(builder(dataset, config, context))

                # Lazy import — reports.render imports this module.
                from reports.render import render_fragment

                return render_fragment(body_html, enriched, label=f"body ({body_type})")

        # Python fallback — used when body_html is blank OR for
        # ``department_templates`` (which always uses sub-templates).
        try:
            builder = cls.REGISTRY[body_type]
        except KeyError:
            raise UnknownBodyType(
                f"Không hỗ trợ body_type '{body_type}'. "
                f"Các giá trị hợp lệ: {', '.join(sorted(cls.REGISTRY))}"
            ) from None
        return builder(dataset, config, context)

    @classmethod
    def has_template_support(cls, body_type: str) -> bool:
        """Whether a user-written ``body_html`` is honoured for this body type."""
        return body_type in cls._CONTEXT_BUILDERS

    @classmethod
    def available(cls) -> list[str]:
        return sorted(cls.REGISTRY)
