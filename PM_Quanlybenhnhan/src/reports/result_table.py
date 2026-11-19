"""
Per-patient result table renderer (shared by templates and the public portal).

Kept in its own module so both ``render.py`` (context variable) and
``report_tags.py`` (custom template tag) can import it without a circular
import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from reports.report_builder import PatientRecord


def render_company_summary_table(dataset, config=None) -> str:
    """
    Render a flat company-summary table: one row per employee.

    Reuses ``dataset.table`` (the legacy flat ``ReportData``) so columns follow
    the package order — personal info first, then every department field, then
    the conclusion columns. No merged/grouped headers (single header row).

    config:
        show_normal_range (bool, default True) — append "(min - max)" to field labels
        highlight_abnormal (bool, default True) — bold/red out-of-range values
    """
    config = config or {}
    show_range = config.get("show_normal_range", True)
    highlight = config.get("highlight_abnormal", True)

    table = getattr(dataset, "table", None)
    if table is None or not table.headers.columns:
        return '<p class="empty">Chưa có dữ liệu.</p>'

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

    columns = table.headers.columns

    # ── Header (single flat row) ──
    header_cells: list[str] = []
    for c in columns:
        if c.field:
            label = c.field.label
            if c.field.unit:
                label = f"{label} ({c.field.unit})"
            if show_range and c.field.normal_range:
                label = f"{label} ({c.field.normal_range})"
            header_cells.append(label)
        else:
            header_cells.append(c.header_personal or "")

    # ── Body rows ──
    body_rows: list[str] = []
    for row in table.rows:
        cells: list[str] = []
        for c in columns:
            if c.field:
                value = row.get(c.field.field_key, "")
                abnormal = highlight and _is_out_of_range(
                    value, c.field.normal_min, c.field.normal_max
                )
                cls = ' class="abnormal"' if abnormal else ""
                cells.append(f"<td{cls}>{value}</td>")
            else:
                key = personal_key_map.get(c.header_personal or "", "")
                cells.append(f"<td>{row.get(key, '')}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    thead = "".join(f"<th>{h}</th>" for h in header_cells)
    return (
        '<table class="report-table">'
        f"<thead><tr>{thead}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


def _is_out_of_range(value, nmin, nmax) -> bool:
    """Whether a numeric value falls outside ``[nmin, nmax]``."""
    if value in (None, ""):
        return False
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return False
    if nmin is not None and number < nmin:
        return True
    return bool(nmax is not None and number > nmax)


def _esc(value) -> str:
    """HTML-escape a value for table output."""
    if value is None:
        return ""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _money(value) -> str:
    """Format a numeric amount with thousand separators (dots)."""
    try:
        from decimal import Decimal

        return f"{Decimal(str(value)):,.0f}".replace(",", ".")
    except Exception:
        return str(value or "")


def _priced_items(dataset) -> list[tuple[str, int]]:
    """Return ordered ``(label, price)`` for fields with a non-zero price."""
    import uuid as _uuid

    from examinations.models import DepartmentField

    ordered: list[tuple[str, str, str]] = []
    for spec in dataset.departments:
        tid = spec.template_id
        if not tid:
            continue
        try:
            _uuid.UUID(str(tid))
        except (ValueError, AttributeError, TypeError):
            continue
        for f in spec.fields:
            ordered.append((str(tid), f.field_key, f.label))

    template_ids = list({t for t, _, _ in ordered})
    prices: dict[tuple[str, str], int] = {}
    if template_ids:
        for f in DepartmentField.objects.filter(template_id__in=template_ids):
            prices[(str(f.template_id), f.key)] = int(f.default_price or 0)

    items: list[tuple[str, int]] = []
    seen: set[tuple[str, str]] = set()
    for tid, key, label in ordered:
        k = (tid, key)
        if k in seen:
            continue
        seen.add(k)
        price = prices.get(k, 0)
        if price:
            items.append((label, price))
    return items


def render_cost_table(dataset, config=None) -> str:
    """
    Render a per-employee cost table.

    - ``per_field`` pricing: one column per priced field, one row per employee.
    - ``package_total`` pricing: a single "Gói khám" column with the flat price.

    Columns: STT, Số hồ sơ, Mã NV, Họ và tên, Ngày sinh, Giới tính, [items…], TỔNG.
    """
    cep = dataset.company_exam_package
    pricing_mode = getattr(cep, "pricing_mode", "per_field") if cep else "per_field"

    basic_cols = [
        ("stt", "STT"),
        ("so_ho_so", "Số hồ sơ"),
        ("ma_nv", "Mã NV"),
        ("ho_ten", "Họ và tên"),
        ("ngay_sinh", "Ngày sinh"),
        ("gioi_tinh", "Giới tính"),
    ]

    if pricing_mode == "package_total":
        package_price = int(dataset.exam_package.default_package_price or 0)
        items = [("Gói khám", package_price)]
    else:
        items = _priced_items(dataset)

    header = [label for _, label in basic_cols] + [label for label, _ in items] + ["TỔNG"]

    body_rows: list[str] = []
    for p in dataset.patients:
        cells = [
            p.stt, p.so_ho_so, p.ma_nv, p.ho_ten, p.ngay_sinh, p.gioi_tinh_display,
        ]
        subtotal = 0
        for _, price in items:
            cells.append(_money(price) if price else "-")
            subtotal += price
        cells.append(_money(subtotal))
        tds = "".join(
            f'<td class="num">{_esc(v)}</td>' if i >= len(basic_cols)
            else f"<td>{_esc(v)}</td>"
            for i, v in enumerate(cells)
        )
        body_rows.append(f"<tr>{tds}</tr>")

    if not body_rows:
        return '<p class="empty">Chưa có dữ liệu.</p>'

    thead = "".join(f"<th>{_esc(h)}</th>" for h in header)
    return (
        '<table class="report-table cost-table">'
        f"<thead><tr>{thead}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


def render_result_table_html(patient: "PatientRecord") -> str:
    """
    Build a per-field result table for one patient.

    Columns: Danh mục khám / Kết quả / Khoảng tham chiếu / Ghi chú.
    """
    parts: list[str] = []
    for dept in patient.departments:
        filled = [f for f in dept.fields if not f.is_empty]
        if not filled:
            continue
        parts.append(
            f'<tr class="dept-header"><td colspan="4">{dept.name}</td></tr>'
        )
        for f in filled:
            value = str(f.value)
            unit = f.unit or ""
            result = f"{value} ({unit})" if unit else value
            abnormal_class = "abnormal" if f.is_abnormal else ""
            note = ""
            if f.abnormal_direction == "low":
                note = "Thấp"
            elif f.abnormal_direction == "high":
                note = "Cao"
            reference = f.normal_range or "—"
            parts.append(
                '<tr>'
                f'<td>{f.label}</td>'
                f'<td class="{abnormal_class}">{result}</td>'
                f'<td>{reference}</td>'
                f'<td>{note}</td>'
                '</tr>'
            )

    if not parts:
        return '<p class="empty">Chưa có dữ liệu kết quả khám.</p>'

    return (
        '<table class="report-table">'
        '<thead><tr>'
        '<th>Danh mục khám</th><th>Kết quả</th>'
        '<th>Khoảng tham chiếu</th><th>Ghi chú</th>'
        '</tr></thead><tbody>'
        + "".join(parts)
        + "</tbody></table>"
    )
