"""SVG charts for the company-summary report (print-safe, no JavaScript)."""

from __future__ import annotations

import json
import math
from html import escape
from typing import Any, Sequence

_COLORS = (
    "#0A7C6E",
    "#4A90D9",
    "#F39C12",
    "#E74C3C",
    "#8E44AD",
    "#16A085",
    "#2980B9",
    "#D35400",
    "#27AE60",
    "#7F8C8D",
)


def pie_chart_svg(
    items: Sequence[tuple[str, float]],
    title: str = "",
    *,
    size: int = 160,
) -> str:
    """Return a pie chart + legend. ``items`` is ``(label, value)``."""
    series = [(label, float(value)) for label, value in items if value > 0]
    payload = [{"label": label, "value": value} for label, value in series]
    if not series:
        return _wrap(
            title, "pie", payload, '<p class="empty">Không có dữ liệu biểu đồ.</p>'
        )

    total = sum(value for _, value in series)
    cx = cy = size / 2
    radius = size / 2 - 4
    angle = -math.pi / 2
    slices: list[str] = []

    for idx, (_, value) in enumerate(series):
        sweep = value / total * 2 * math.pi
        end = angle + sweep
        color = _COLORS[idx % len(_COLORS)]
        slices.append(_arc_path(cx, cy, radius, angle, end, color))
        angle = end

    legend_rows = []
    for idx, (label, value) in enumerate(series):
        color = _COLORS[idx % len(_COLORS)]
        pct = value / total * 100
        legend_rows.append(
            f'<div class="chart-legend-row">'
            f'<span class="chart-swatch" style="background:{color}"></span>'
            f"<span>{escape(str(label))} — {pct:.1f}%</span></div>"
        )

    svg = (
        f'<svg class="chart-svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">'
        f"{''.join(slices)}</svg>"
        f'<div class="chart-legend">{"".join(legend_rows)}</div>'
    )
    return _wrap(title, "pie", payload, svg)


def bar_chart_svg(
    items: Sequence[tuple[str, float]],
    title: str = "",
    *,
    max_width: int = 220,
) -> str:
    """Horizontal bars. Values are treated as percentages when ≤ 100."""
    series = [(label, float(value)) for label, value in items]
    payload = [{"label": label, "value": value} for label, value in series]
    if not series:
        return _wrap(
            title, "bar", payload, '<p class="empty">Không có dữ liệu biểu đồ.</p>'
        )

    peak = max((value for _, value in series), default=0) or 1
    rows: list[str] = []
    for idx, (label, value) in enumerate(series):
        color = _COLORS[idx % len(_COLORS)]
        width = max(2, int(value / peak * max_width))
        rows.append(
            f'<div class="chart-bar-row">'
            f'<span class="chart-bar-label">{escape(str(label))}</span>'
            f'<span class="chart-bar" style="width:{width}px;background:{color}"></span>'
            f'<span class="chart-bar-value">{value:.1f}%</span></div>'
        )
    return _wrap(title, "bar", payload, "".join(rows))


def _arc_path(
    cx: float, cy: float, radius: float, start: float, end: float, color: str
) -> str:
    if abs(end - start) >= 2 * math.pi - 1e-6:
        # Full circle — two semicircles, a single arc cannot draw 360°.
        return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{radius:.2f}" fill="{color}"/>'
    large = 1 if (end - start) > math.pi else 0
    x1 = cx + radius * math.cos(start)
    y1 = cy + radius * math.sin(start)
    x2 = cx + radius * math.cos(end)
    y2 = cy + radius * math.sin(end)
    return (
        f'<path fill="{color}" d="M {cx:.2f} {cy:.2f} '
        f"L {x1:.2f} {y1:.2f} "
        f'A {radius:.2f} {radius:.2f} 0 {large} 1 {x2:.2f} {y2:.2f} Z"/>'
    )


def _wrap(
    title: str, chart_type: str, payload: list[dict[str, Any]], inner: str
) -> str:
    marker = escape(
        json.dumps(
            {"type": chart_type, "title": title, "items": payload}, ensure_ascii=False
        ),
        quote=True,
    )
    heading = f"<h6>{escape(title)}</h6>" if title else ""
    return (
        f'<figure class="report-chart" data-chart="{marker}">'
        f'{heading}<div class="chart-body">{inner}</div></figure>'
    )


def parse_chart_attr(raw: str | None) -> dict[str, Any] | None:
    """Decode a ``data-chart`` HTML attribute into ``{type, title, items}``."""
    from html import unescape

    if not raw:
        return None
    try:
        payload = json.loads(unescape(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    items = payload.get("items") or []
    if not isinstance(items, list):
        return None
    return {
        "type": str(payload.get("type") or "pie"),
        "title": str(payload.get("title") or ""),
        "items": [
            {
                "label": str(item.get("label", "")),
                "value": float(item.get("value") or 0),
            }
            for item in items
            if isinstance(item, dict)
        ],
    }


#: Column where Excel chart source data is parked (outside the 15-col body grid).
_EXCEL_CHART_DATA_COL = 20
_EXCEL_CHART_ROWS = 14


def add_openpyxl_chart(
    ws: Any,
    payload: dict[str, Any],
    start_row: int,
    *,
    start_col: int = 1,
    width_columns: int | None = None,
    data_col: int = _EXCEL_CHART_DATA_COL,
) -> int:
    """
    Write chart source data off to the right and place an openpyxl chart.

    Returns the next free row below the chart's visual footprint.
    """
    from openpyxl.chart import BarChart, PieChart, Reference
    from openpyxl.chart.label import DataLabelList
    from openpyxl.chart.series import DataPoint
    from openpyxl.utils import get_column_letter

    items = [item for item in (payload.get("items") or []) if item.get("value")]
    title = payload.get("title") or ""
    chart_type = payload.get("type") or "pie"
    if not items:
        if title:
            ws.cell(row=start_row, column=start_col, value=title)
            return start_row + 1
        return start_row

    label_col = data_col
    value_col = data_col + 1
    ws.cell(row=start_row, column=label_col, value="label")
    ws.cell(row=start_row, column=value_col, value="value")
    for offset, item in enumerate(items, start=1):
        ws.cell(row=start_row + offset, column=label_col, value=item["label"])
        ws.cell(row=start_row + offset, column=value_col, value=item["value"])

    n = len(items)
    cats = Reference(
        ws, min_col=label_col, min_row=start_row + 1, max_row=start_row + n
    )
    data = Reference(ws, min_col=value_col, min_row=start_row, max_row=start_row + n)

    if chart_type == "bar":
        chart = BarChart()
        chart.type = "bar"
        chart.style = 10
        chart.y_axis.title = None
        chart.x_axis.title = None
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
    else:
        chart = PieChart()
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        chart.dataLabels = DataLabelList()
        chart.dataLabels.showPercent = True
        chart.dataLabels.showVal = False
        chart.dataLabels.showCatName = False
        # Match HTML palette when possible.
        series = chart.series[0]
        for idx in range(n):
            pt = DataPoint(idx=idx)
            color = _COLORS[idx % len(_COLORS)].lstrip("#")
            pt.graphicalProperties.solidFill = color
            series.data_points.append(pt)

    if title:
        chart.title = title
    chart.width = max(4.0, width_columns * 2.2) if width_columns else 14
    chart.height = 8
    ws.add_chart(chart, f"{get_column_letter(start_col)}{start_row}")

    for col in (label_col, value_col):
        ws.column_dimensions[get_column_letter(col)].hidden = True

    return start_row + _EXCEL_CHART_ROWS
