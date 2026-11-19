from __future__ import annotations

import io
import logging
import re
import unicodedata
from datetime import date

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from pathlib import Path

from accounts.models import CompanyExamPackage
from reports.report_builder import ReportData, build_clinical_detail_report

logger = logging.getLogger(__name__)


def _html_to_excel_rows(html: str) -> list[dict]:
    """
    Parse simple HTML into a list of row descriptors for per-row rendering.

    Each descriptor is either:
      ``{"type": "text", "value": str, "font": Font}``
      ``{"type": "image", "src": str}``

    Block-level elements (``<div>``, ``<p>``, ``<h1>``-``<h4>``) each become
    one row.  ``<img>`` inside a block produces an image row placed inline.
    ``<br>`` inside a block produces a ``\\n`` within that row's text.
    """
    from html.parser import HTMLParser

    rows: list[dict] = []
    current_text: list[str] = []
    current_font: Font | None = None
    default_font = Font(size=12)

    def _flush_text():
        if current_text:
            value = "".join(current_text).strip()
            current_text.clear()
            if value:
                rows.append(
                    {
                        "type": "text",
                        "value": value,
                        "font": current_font or default_font,
                    }
                )

    class _Parser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            nonlocal current_font
            a = dict(attrs)
            if tag == "img":
                src = a.get("src", "")
                if src:
                    rows.append({"type": "image", "src": src})
                return
            if tag in ("br",):
                current_text.append("\n")
                return
            if tag in ("div", "p", "h1", "h2", "h3", "h4"):
                _flush_text()
                style = a.get("style", "")
                current_font = _parse_font_from_style(style) or default_font
                if tag == "h1":
                    current_font = current_font.copy(size=18, bold=True)
                elif tag == "h2":
                    current_font = current_font.copy(size=16, bold=True)
                elif tag == "h3":
                    current_font = current_font.copy(size=14, bold=True)
                elif tag == "h4":
                    current_font = current_font.copy(size=12, bold=True)

        def handle_data(self, data):
            current_text.append(data)

        def handle_endtag(self, tag):
            if tag in ("div", "p", "h1", "h2", "h3", "h4"):
                _flush_text()

    parser = _Parser()
    cleaned = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.S)
    parser.feed(cleaned)
    _flush_text()

    return rows


def _resolve_image_src(src: str) -> str | None:
    """Convert an HTML img src to a local filesystem path openpyxl can read."""
    if not src:
        return None
    if src.startswith("file://"):
        from urllib.parse import urlparse

        parsed = urlparse(src)
        path = parsed.path
        import platform

        if platform.system() == "Windows" and path.startswith("/"):
            path = path[1:]
        if path and Path(path).exists():
            return path
    if src.startswith(("http://", "https://")):
        return None
    # Relative path — resolve against MEDIA_ROOT.
    media_url = str(settings.MEDIA_URL)
    if media_url and src.startswith(media_url):
        relative = src[len(media_url) :]
        full = Path(settings.MEDIA_ROOT) / relative
        if full.exists():
            return str(full)
    # Try as absolute filesystem path.
    if Path(src).exists():
        return src
    return None


def _parse_font_from_style(style: str) -> Font | None:
    """Extract font-size and font-weight from a CSS style string."""
    import re

    size = None
    bold = False
    m = re.search(r"font-size\s*:\s*(\d+(?:\.\d+)?)pt", style)
    if m:
        size = int(float(m.group(1)))
    if "font-weight:bold" in style.replace(" ", "") or "font-weight: bold" in style:
        bold = True
    if size is not None or bold:
        return Font(size=size or 12, bold=bold)
    return None


def _parse_text_align(style: str) -> str | None:
    """Extract ``text-align`` from a CSS style string, if present."""
    import re

    m = re.search(r"text-align\s*:\s*(left|center|right)", style)
    return m.group(1) if m else None


def _parse_font_size(style: str) -> int | None:
    """Extract ``font-size`` (in pt) from a CSS style string, if present."""
    import re

    m = re.search(r"font-size\s*:\s*(\d+(?:\.\d+)?)pt", style)
    return int(float(m.group(1))) if m else None


def _parse_font_bold(style: str) -> bool:
    """Return True when a CSS style string declares bold weight."""
    return "font-weight:bold" in style.replace(" ", "") or "font-weight: bold" in style


#: Excel body text when HTML omits ``font-size``.
DEFAULT_EXCEL_FONT_SIZE = 12


def _font_from_text_block(block: dict) -> Font:
    """Excel font from a parsed text block (inline CSS ``font-size`` / ``font-weight``)."""
    return Font(
        size=block.get("size") or DEFAULT_EXCEL_FONT_SIZE,
        bold=bool(block.get("bold")),
    )


def _alignment_from_text_block(block: dict) -> Alignment:
    """Excel alignment from a parsed text block (inline CSS ``text-align``)."""
    return Alignment(
        horizontal=block.get("align") or "left",
        vertical="center",
        wrap_text=True,
    )


def _parse_css_length_pt(value: str) -> float | None:
    """Convert a CSS length (``pt`` / ``px`` / bare number) to Excel points."""
    raw = (value or "").strip().lower()
    if not raw:
        return None
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(pt|px)?$", raw)
    if not m:
        return None
    amount = float(m.group(1))
    unit = m.group(2) or "pt"
    if unit == "px":
        amount *= 0.75
    if amount <= 0:
        return None
    return amount


def _parse_row_height(attrs: dict | None = None, style: str = "") -> float | None:
    """Read Excel row height from ``data-row-height`` or CSS ``height`` / ``min-height``.

    Preferred units are points (``pt``), matching Excel ``row_dimensions.height``.
    ``px`` is accepted and converted (1px ≈ 0.75pt). A bare number is treated as pt.
    """
    attrs = attrs or {}
    raw_attr = attrs.get("data-row-height")
    if raw_attr not in (None, ""):
        height = _parse_css_length_pt(str(raw_attr))
        if height is not None:
            return height

    css = style or attrs.get("style", "") or ""
    for prop in ("height", "min-height"):
        m = re.search(rf"{prop}\s*:\s*([^;]+)", css, flags=re.I)
        if not m:
            continue
        height = _parse_css_length_pt(m.group(1))
        if height is not None:
            return height
    return None


def _apply_row_height(ws, row: int, height: float | None) -> None:
    """Set an Excel row height when ``height`` is a positive point value."""
    if height is None or height <= 0:
        return
    ws.row_dimensions[row].height = float(height)


#: Blank Excel rows between letterhead and body when HTML omits
#: ``data-excel-header-gap`` (matches historical ``header_rows + 2``).
DEFAULT_EXCEL_HEADER_GAP_ROWS = 1


def _parse_excel_header_gap(html: str) -> int:
    """Read ``data-excel-header-gap`` from rendered HTML (default 1 blank row).

    Example::

        <div data-excel-header-gap="9"></div>

    The value is the number of empty rows between the last header cell row and
    the first body row after letterhead merge. Values below 0 are clamped to 0.
    """
    if not html:
        return DEFAULT_EXCEL_HEADER_GAP_ROWS
    m = re.search(
        r"""data-excel-header-gap\s*=\s*(?:["']?)(\d+)""",
        html,
        flags=re.I,
    )
    if not m:
        return DEFAULT_EXCEL_HEADER_GAP_ROWS
    return max(0, int(m.group(1)))


def _letterhead_body_start(header_rows: int, header_gap_rows: int) -> int:
    """1-based Excel row where body content begins under a letterhead."""
    if header_rows <= 0:
        return 1
    return header_rows + 1 + max(0, int(header_gap_rows))


def _parse_excel_gap(attrs: dict | None) -> int:
    """Read ``data-excel-gap`` (blank Excel rows to insert before this element)."""
    if not attrs:
        return 0
    raw = attrs.get("data-excel-gap")
    if raw in (None, ""):
        return 0
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


class _HtmlTableRow(list):
    """Parsed ``<tr>``: a list of cells plus optional Excel row height in points."""

    def __init__(self, *args, height: float | None = None) -> None:
        super().__init__(*args)
        self.height = height


def _fit_image(img, max_w: int, max_h: int) -> None:
    """Scale an openpyxl image into a bounding box, preserving aspect ratio."""
    w = img.width
    h = img.height
    if not w or not h:
        return
    scale = min(max_w / w, max_h / h, 1.0)
    img.width = int(w * scale)
    img.height = int(h * scale)


def _write_header_blocks(
    ws, blocks: list[dict], total_cols: int, current_row: int
) -> int:
    """Render header blocks (text/image/table) into the sheet."""
    for block in blocks:
        if block["type"] == "table":
            current_row = _write_header_table(
                ws, block["rows"], total_cols, current_row
            )
        elif block["type"] == "text":
            if total_cols > 1:
                ws.merge_cells(
                    start_row=current_row,
                    start_column=1,
                    end_row=current_row,
                    end_column=total_cols,
                )
            c = ws.cell(row=current_row, column=1, value=block["value"])
            c.font = _font_from_text_block(block)
            c.alignment = _alignment_from_text_block(block)
            _apply_row_height(ws, current_row, block.get("height"))
            current_row += 1
        elif block["type"] == "image":
            path = _resolve_image_src(block["src"])
            if path:
                try:
                    img = XLImage(path)
                    _fit_image(img, 240, 80)
                    ws.add_image(img, f"A{current_row}")
                    current_row += 2
                except Exception as e:  # pragma: no cover
                    logger.warning("Image insert failed: %s", e)
    return current_row


def _write_header_table(ws, rows: list, total_cols: int, start_row: int) -> int:
    """Render a letterhead table: logo image left, text aligned per cell style.

    Supports ``rowspan`` on the logo cell so subsequent rows keep text in
    column 2+ while the image occupies column A across multiple rows.
    """
    current_row = start_row
    logo_rows_remaining = 0
    for tr in rows:
        image_cells = [c for c in tr if c.get("image")]
        has_image = bool(image_cells)
        if has_image:
            logo_rows_remaining = max(
                (int(c.get("rowspan") or 1) for c in image_cells),
                default=1,
            )

        text_cells = [c for c in tr if c.get("text")]
        logo_occupies_col = has_image or logo_rows_remaining > 0

        for cell in image_cells:
            path = _resolve_image_src(cell["image"])
            if path:
                try:
                    img = XLImage(path)
                    # Taller box when logo spans 2+ header rows.
                    max_h = 80 * max(int(cell.get("rowspan") or 1), 1)
                    _fit_image(img, 240, max_h)
                    ws.add_image(img, f"A{current_row}")
                except Exception as e:  # pragma: no cover
                    logger.warning("Image insert failed: %s", e)

        if text_cells:
            runs: list[dict] = []
            for tc in text_cells:
                runs.extend(
                    tc.get("runs")
                    or [{"text": tc["text"], "size": None, "bold": False}]
                )
            align = (
                next((c.get("align") for c in text_cells if c.get("align")), None)
                or "left"
            )
            start_col = 2 if logo_occupies_col else 1
            if start_col <= total_cols:
                ws.merge_cells(
                    start_row=current_row,
                    start_column=start_col,
                    end_row=current_row,
                    end_column=total_cols,
                )
                c = ws.cell(row=current_row, column=start_col)
            else:
                c = ws.cell(row=current_row, column=1)
            c.alignment = Alignment(horizontal=align, vertical="center", wrap_text=True)

            if len(runs) > 1:
                from openpyxl.cell.rich_text import CellRichText, TextBlock
                from openpyxl.cell.text import InlineFont

                rich = CellRichText()
                for i, r in enumerate(runs):
                    sep = "\n" if i < len(runs) - 1 else ""
                    rich.append(
                        TextBlock(
                            InlineFont(
                                sz=r.get("size") or DEFAULT_EXCEL_FONT_SIZE,
                                b=r.get("bold", False),
                            ),
                            r["text"] + sep,
                        )
                    )
                c.value = rich
            else:
                r = runs[0] if runs else {}
                c.value = "\n".join(x["text"] for x in runs)
                c.font = Font(
                    size=r.get("size") or DEFAULT_EXCEL_FONT_SIZE,
                    bold=r.get("bold", False),
                )

        if logo_rows_remaining > 0:
            logo_rows_remaining -= 1
        _apply_row_height(ws, current_row, getattr(tr, "height", None))
        current_row += 1
    return current_row


def _build_clinical_detail_excel(
    report_data: ReportData,
    company_name: str,
    exam_date: str = "",
    exam_package_name: str = "",
    *,
    use_clinic_header: bool = True,
    header_xlsx: str | None = None,
    footer_xlsx: str | None = None,
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Báo cáo chi tiết"

    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    header_font = Font(bold=True, size=10)
    wrap_align = Alignment(wrap_text=True, vertical="center", horizontal="center")
    header_fill = PatternFill(
        start_color="D9EAD3", end_color="D9EAD3", fill_type="solid"
    )

    cols = report_data.headers.columns
    current_row = 1

    # Legacy clinic text header (only when no uploaded Excel letterhead).
    if use_clinic_header and not header_xlsx:
        clinic = getattr(settings, "CLINIC_INFO", {}) or {}
        lines = [clinic.get("name", "")]
        if clinic.get("address"):
            lines.append(f"Địa chỉ: {clinic['address']}")
        if clinic.get("phone"):
            lines.append(f"SĐT: {clinic['phone']}")
        header = "\n".join(filter(None, lines))
        if header.strip():
            ws.merge_cells(
                start_row=current_row,
                start_column=1,
                end_row=current_row,
                end_column=len(cols),
            )
            c = ws.cell(row=current_row, column=1, value=header)
            c.font = Font(bold=True, size=12)
            c.alignment = Alignment(horizontal="center", vertical="center")
            current_row += 1

    current_row += 1  # blank row before table headers

    # ── Row R7: Parent department headers ──
    row_r7 = current_row
    for ci, col in enumerate(cols, 1):
        if col.field and col.merge_parent:
            if col.parent_span > 1:
                ws.merge_cells(
                    start_row=row_r7,
                    start_column=ci,
                    end_row=row_r7,
                    end_column=ci + col.parent_span - 1,
                )
            c = ws.cell(
                row=row_r7,
                column=ci,
                value=col.field.parent_name or col.field.department_name,
            )
            c.font = header_font
            c.alignment = wrap_align
            c.fill = header_fill
            c.border = thin_border
        elif not col.field:
            c = ws.cell(row=row_r7, column=ci, value="")
            c.border = thin_border

    # ── Row R8: Department headers ──
    row_r8 = current_row + 1
    for ci, col in enumerate(cols, 1):
        if col.field and col.merge_child:
            if col.child_span > 1:
                ws.merge_cells(
                    start_row=row_r8,
                    start_column=ci,
                    end_row=row_r8,
                    end_column=ci + col.child_span - 1,
                )
            c = ws.cell(row=row_r8, column=ci, value=col.field.department_name)
            c.font = header_font
            c.alignment = wrap_align
            c.fill = header_fill
            c.border = thin_border
        elif not col.field:
            c = ws.cell(row=row_r8, column=ci, value="")
            c.font = header_font
            c.alignment = wrap_align
            c.fill = header_fill
            c.border = thin_border

    # ── Row R9: Field labels ──
    row_r9 = current_row + 2
    for ci, col in enumerate(cols, 1):
        if col.field:
            label = col.field.label
            if col.field.unit:
                label += f" ({col.field.unit})"
            c = ws.cell(row=row_r9, column=ci, value=label)
        else:
            c = ws.cell(row=row_r9, column=ci, value=col.header_personal)
        c.font = Font(bold=True, size=8)
        c.alignment = wrap_align
        c.border = thin_border

    # ── Row R10: Normal ranges ──
    row_r10 = current_row + 3
    for ci, col in enumerate(cols, 1):
        if col.field and col.field.normal_range:
            c = ws.cell(row=row_r10, column=ci, value=col.field.normal_range)
        else:
            c = ws.cell(row=row_r10, column=ci, value="")
        c.font = Font(size=8, italic=True, color="888888")
        c.alignment = wrap_align
        c.border = thin_border

    # ── Data rows ──
    for ri, row_data in enumerate(report_data.rows, current_row + 4):
        for ci, col in enumerate(cols, 1):
            if col.field:
                value = row_data.get(col.field.field_key, "")
            elif col.header_personal == "STT":
                value = row_data.get("stt", "")
            elif col.header_personal == "Số hồ sơ":
                value = row_data.get("so_ho_so", "")
            elif col.header_personal == "Mã NV":
                value = row_data.get("ma_nv", "")
            elif col.header_personal == "Họ và tên":
                value = row_data.get("ho_ten", "")
            elif col.header_personal == "Ngày sinh":
                value = row_data.get("ngay_sinh", "")
            elif col.header_personal == "Giới tính":
                value = row_data.get("gioi_tinh", "")
            elif col.header_personal == "Bộ phận":
                value = row_data.get("bo_phan", "")
            elif col.header_personal == "CCCD":
                value = row_data.get("cccd", "")
            elif col.header_personal == "Nơi ở hiện tại":
                value = row_data.get("noi_o", "")
            elif col.header_personal == "Ngày bắt đầu làm việc":
                value = row_data.get("ngay_vao", "")
            elif col.header_personal == "Phân loại sức khỏe":
                value = row_data.get("phan_loai", "")
            elif col.header_personal == "Bệnh mắc":
                value = row_data.get("benh_mac", "")
            elif col.header_personal == "Tư vấn":
                value = row_data.get("tu_van", "")
            elif col.header_personal == "Kết luận":
                value = row_data.get("ket_luan", "")
            else:
                value = ""

            c = ws.cell(row=ri, column=ci, value=value)
            c.border = thin_border
            c.font = Font(size=10)
            c.alignment = Alignment(vertical="center", wrap_text=True)

    # Column widths
    for ci in range(1, len(cols) + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 12

    from reports.xlsx_letterhead import (
        apply_letterhead,
        media_path,
        restore_letterhead_drawings,
    )

    wb = apply_letterhead(wb, header_xlsx, footer_xlsx)

    output = io.BytesIO()
    wb.save(output)
    file_bytes = output.getvalue()
    # openpyxl strips grouped shapes/frames — put them back from the upload.
    file_bytes = restore_letterhead_drawings(file_bytes, header_xlsx)
    if not header_xlsx:
        file_bytes = restore_letterhead_drawings(file_bytes, footer_xlsx)
    return file_bytes


REPORT_TYPE_LABELS = {
    "clinical_detail": "Bao_cao_chi_tiet",
    "company_summary": "Bao_cao_tong_hop",
    "occupational": "Bao_cao_benh_nghe_nghiep",
    "cost": "Bao_cao_chi_phi",
}


def _slugify_filename(value: str) -> str:
    """ASCII-safe filename fragment (Django storage chokes on some unicode)."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", ascii_only).strip("_")
    return cleaned or "report"


@shared_task
def generate_report_task(report_id: str) -> None:
    from reports.models import Report

    try:
        report = Report.objects.select_related("company", "template").get(id=report_id)
    except Report.DoesNotExist:
        logger.warning(
            "Report %s no longer exists, skipping generate_report_task",
            report_id,
        )
        return

    try:
        params = report.parameters or {}
        exam_package_id = params.get("exam_package_id")
        exam_date = params.get("exam_date")

        cep = CompanyExamPackage.objects.select_related("exam_package", "company").get(
            company=report.company,
            exam_package_id=exam_package_id,
            is_active=True,
        )

        # Auto-fill diagnosis conclusions for any unconcluded exams so reports
        # always reflect up-to-date findings (mirrors the scheduled scan).
        from diagnosis.tasks import run_package_diagnosis

        run_package_diagnosis(cep)

        if report.template_id:
            if report.output_format == Report.FORMAT_EXCEL:
                file_bytes, ext = _render_excel_with_template(report, cep, exam_date)
            else:
                file_bytes, ext = _render_with_template(report, cep, exam_date)
        else:
            file_bytes, ext = _render_legacy_excel(report, cep, exam_date)

        label = REPORT_TYPE_LABELS.get(report.report_type, "Bao_cao")
        filename = (
            f"{_slugify_filename(report.company.name)}"
            f"_{_slugify_filename(cep.exam_package.name)}"
            f"_{label}_{date.today().isoformat()}.{ext}"
        )
        report.file.save(filename, ContentFile(file_bytes), save=False)
        report.status = Report.STATUS_DONE
        report.error_message = ""
        report.save()

        # Also ensure every employee in this package has a per-employee report
        # accessible via /kq/{public_id}/.
        _ensure_employee_reports(cep, exam_date, report.created_by)

    except Exception as e:
        logger.exception("Report %s generation failed", report_id)
        report.status = Report.STATUS_FAILED
        report.error_message = str(e)
        report.save()


def _render_with_template(report, cep, exam_date: str | None) -> tuple[bytes, str]:
    """Dynamic template path (Sprint 9a): HTML output only."""
    from reports.render import render_report
    from reports.report_builder import build_report_dataset

    dataset = build_report_dataset(cep, exam_date=exam_date)
    html = render_report(report.template, dataset, report=report)

    return html.encode("utf-8"), "html"


def _parse_html_to_blocks(html: str) -> list[dict]:
    """
    Parse an HTML document into ordered blocks: text, image, table, or chart.

    ``<style>``/``<script>``/``<head>`` content is skipped. Tables become
    ``{"type": "table", "rows": [[cell, ...], ...]}`` where each cell carries
    ``text``, ``colspan``, ``rowspan`` and style flags (``header``, ``abnormal``,
    ``dept_header``). Each ``<tr>`` may also carry ``height`` (Excel points) via
    ``style="height:…pt"`` or ``data-row-height``. Text blocks may carry the same.
    ``<figure class="report-chart" data-chart="…">`` becomes
    ``{"type": "chart", "payload": {type, title, items}}`` (SVG children ignored).

    Blocks inside ``<div class="report-row">`` can opt into the fixed Excel grid
    with ``data-column`` and ``data-width``. They receive shared ``layout_row``
    metadata so the workbook writer can place them side-by-side.
    ``data-excel-gap="N"`` on a block element becomes
    ``{"type": "gap", "rows": N}`` (N blank Excel rows before that element).
    """
    from html.parser import HTMLParser

    from reports.charts import parse_chart_attr

    blocks: list[dict] = []

    class _Parser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self._skip_depth = 0
            self._chart_depth = 0
            self._table: list | None = None
            self._row: _HtmlTableRow | None = None
            self._cell: dict | None = None
            self._cell_runs: list[dict] = []
            self._cell_text: list[str] = []
            self._cell_size: int | None = None
            self._cell_bold: bool = False
            self._block_text: list[str] = []
            self._block_align: str | None = None
            self._block_size: int | None = None
            self._block_bold: bool = False
            self._block_height: float | None = None
            self._layout_row: int | None = None
            self._layout_item: tuple[int, int] | None = None
            self._layout_sequence = 0
            self._div_markers: list[str] = []

        def _append_block(self, block: dict) -> None:
            if self._layout_row is not None and self._layout_item is not None:
                block["layout_row"] = self._layout_row
                block["layout_col"], block["layout_span"] = self._layout_item
            blocks.append(block)

        def _flush_block(self) -> None:
            text = "".join(self._block_text).strip()
            if text:
                self._append_block(
                    {
                        "type": "text",
                        "value": text,
                        "align": self._block_align,
                        "size": self._block_size,
                        "bold": self._block_bold,
                        "height": self._block_height,
                    }
                )
            self._block_text = []
            self._block_align = None
            self._block_size = None
            self._block_bold = False
            self._block_height = None

        def _flush_cell_run(self) -> None:
            text = "".join(self._cell_text).strip()
            if text:
                self._cell_runs.append(
                    {"text": text, "size": self._cell_size, "bold": self._cell_bold}
                )
            self._cell_text = []

        def handle_starttag(self, tag: str, attrs) -> None:
            a = dict(attrs)
            if tag in ("style", "script", "head"):
                self._skip_depth += 1
                return
            if self._skip_depth:
                return
            if self._chart_depth:
                if tag == "figure":
                    self._chart_depth += 1
                return
            if self._table is None and self._cell is None:
                gap_rows = _parse_excel_gap(a)
                if gap_rows:
                    self._flush_block()
                    # Do not attach report-row layout — gap is a full-width skip.
                    blocks.append({"type": "gap", "rows": gap_rows})
            if tag == "figure":
                payload = parse_chart_attr(a.get("data-chart"))
                if payload is not None:
                    self._flush_block()
                    self._append_block({"type": "chart", "payload": payload})
                    self._chart_depth = 1
                    return
            if tag == "div":
                classes = (a.get("class") or "").split()
                if "report-row" in classes:
                    self._flush_block()
                    self._layout_sequence += 1
                    self._layout_row = self._layout_sequence
                    self._layout_item = None
                    self._div_markers.append("row")
                    return
                if self._layout_row is not None and (
                    "report-grid-item" in classes
                    or "data-column" in a
                    or "data-excel-col" in a
                ):
                    self._flush_block()
                    raw_col = a.get("data-column", a.get("data-excel-col", "1"))
                    raw_span = a.get("data-width", a.get("data-excel-span", "1"))
                    try:
                        column = int(raw_col)
                        span = int(raw_span)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            "report-row yêu cầu data-column và data-width là số nguyên."
                        ) from exc
                    if column < 1 or span < 1:
                        raise ValueError(
                            "report-row yêu cầu data-column và data-width lớn hơn 0."
                        )
                    self._layout_item = (column, span)
                    self._div_markers.append("item")
                    return
                self._div_markers.append("normal")
            if tag == "table":
                self._flush_block()
                self._table = []
            elif tag == "tr" and self._table is not None:
                self._row = _HtmlTableRow(height=_parse_row_height(a))
            elif tag in ("td", "th") and self._row is not None:
                classes = (a.get("class") or "").split()
                self._cell = {
                    "text": "",
                    "colspan": int(a.get("colspan", 1) or 1),
                    "rowspan": int(a.get("rowspan", 1) or 1),
                    "header": tag == "th",
                    "abnormal": "abnormal" in classes,
                    "dept_header": "dept-header" in classes,
                    "align": _parse_text_align(a.get("style", "")),
                }
                self._cell_runs = []
                self._cell_text = []
                self._cell_size = _parse_font_size(a.get("style", ""))
                self._cell_bold = _parse_font_bold(a.get("style", ""))
            elif tag in ("div", "p", "h1", "h2", "h3", "h4"):
                if self._cell is not None:
                    self._flush_cell_run()
                    size = _parse_font_size(a.get("style", ""))
                    if size is not None:
                        self._cell_size = size
                    self._cell_bold = _parse_font_bold(a.get("style", ""))
                else:
                    self._flush_block()
                    align = _parse_text_align(a.get("style", ""))
                    if align:
                        self._block_align = align
                    self._block_size = _parse_font_size(a.get("style", ""))
                    self._block_bold = _parse_font_bold(a.get("style", ""))
                    self._block_height = _parse_row_height(a)
            elif tag == "img":
                src = a.get("src", "")
                if src:
                    if self._cell is not None:
                        self._cell["image"] = src
                    else:
                        self._flush_block()
                        self._append_block({"type": "image", "src": src})
            elif tag == "br":
                if self._cell is not None:
                    self._cell_text.append("\n")
                else:
                    self._block_text.append("\n")

        def handle_data(self, data: str) -> None:
            if self._skip_depth or self._chart_depth:
                return
            if self._cell is not None:
                self._cell_text.append(data)
            elif self._table is None:
                self._block_text.append(data)

        def handle_endtag(self, tag: str) -> None:
            if tag in ("style", "script", "head"):
                self._skip_depth = max(0, self._skip_depth - 1)
                return
            if self._skip_depth:
                return
            if self._chart_depth:
                if tag == "figure":
                    self._chart_depth = max(0, self._chart_depth - 1)
                return
            div_marker = None
            if tag == "div" and self._div_markers:
                div_marker = self._div_markers.pop()
            if tag in ("td", "th") and self._cell is not None:
                self._flush_cell_run()
                self._cell["runs"] = self._cell_runs
                self._cell["text"] = "\n".join(r["text"] for r in self._cell_runs)
                self._row.append(self._cell)
                self._cell = None
                self._cell_runs = []
                self._cell_text = []
            elif tag == "tr" and self._row is not None:
                self._table.append(self._row)
                self._row = None
            elif tag == "table" and self._table is not None:
                self._append_block({"type": "table", "rows": self._table})
                self._table = None
            elif tag in ("div", "p", "h1", "h2", "h3", "h4"):
                if div_marker == "item":
                    self._flush_block()
                    self._layout_item = None
                    return
                if div_marker == "row":
                    self._flush_block()
                    self._layout_item = None
                    self._layout_row = None
                    return
                if self._cell is not None:
                    self._cell_text.append("\n")
                else:
                    self._flush_block()

    parser = _Parser()
    parser.feed(html)
    parser._flush_block()
    return blocks


#: Official company-summary Excel uses a fixed A…O grid so letterhead and body
#: share the same printable width (see documents/Tong Hop báo cáo.xlsx).
COMPANY_SUMMARY_EXCEL_COLUMNS = 15


def _even_column_spans(count: int, total: int) -> list[int]:
    """Distribute ``total`` Excel columns across ``count`` logical columns."""
    if count <= 0:
        return []
    if count >= total:
        return [1] * count
    base, rem = divmod(total, count)
    return [base + (1 if i < rem else 0) for i in range(count)]


def _html_document_to_excel(
    html: str,
    sheet_title: str = "Báo cáo",
    *,
    layout_columns: int | None = None,
) -> tuple[bytes, list[dict]]:
    """Convert a rendered report HTML document into an .xlsx byte payload.

    When ``layout_columns`` is set (company summary uses 15), text rows span the
    full grid and narrow HTML tables are stretched with even colspans so the
    sheet width matches the letterhead.

    Returns ``(xlsx_bytes, chart_specs)`` where each chart spec is
    ``{"payload": dict, "start_row": int}`` (1-based body row). Specs are used
    to re-embed charts after letterhead drawing restore.
    """
    blocks = _parse_html_to_blocks(html)

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]

    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    dept_fill = PatternFill(start_color="EEF4EC", end_color="EEF4EC", fill_type="solid")

    current_row = 1
    max_col = layout_columns or 1
    text_span = layout_columns or None
    chart_specs: list[dict] = []

    from reports.charts import add_openpyxl_chart

    block_index = 0
    chart_index = 0
    while block_index < len(blocks):
        block = blocks[block_index]
        layout_row = block.get("layout_row")
        if layout_row is not None:
            row_blocks = []
            while (
                block_index < len(blocks)
                and blocks[block_index].get("layout_row") == layout_row
            ):
                row_blocks.append(blocks[block_index])
                block_index += 1

            row_height = 1
            grid_width = layout_columns or max(
                max_col,
                max(
                    int(item["layout_col"]) + int(item["layout_span"]) - 1
                    for item in row_blocks
                ),
            )
            occupied_ranges: list[tuple[int, int]] = []
            for row_block in row_blocks:
                start_col = int(row_block["layout_col"])
                span = int(row_block["layout_span"])
                end_col = start_col + span - 1
                if end_col > grid_width:
                    raise ValueError(
                        f"Khối report-row tại cột {start_col}, rộng {span} "
                        f"vượt quá lưới {grid_width} cột."
                    )
                current_range = (start_col, end_col)
                if any(
                    start_col <= used_end and end_col >= used_start
                    for used_start, used_end in occupied_ranges
                ):
                    raise ValueError(
                        f"Các khối report-row bị chồng cột tại {start_col}-{end_col}. "
                        "Mỗi hàng report-row là cạnh nhau trên Excel; "
                        "tiêu đề và bảng cùng cột phải tách thành hai report-row."
                    )
                occupied_ranges.append(current_range)
                if row_block["type"] == "table":
                    table_max_col = _write_html_table(
                        ws,
                        row_block["rows"],
                        current_row,
                        thin_border,
                        dept_fill,
                        layout_columns=span,
                        start_column=start_col,
                        strict_width=True,
                    )
                    max_col = max(max_col, table_max_col)
                    row_height = max(row_height, len(row_block["rows"]))
                elif row_block["type"] == "chart":
                    data_col = 20 + chart_index * 2
                    chart_specs.append(
                        {
                            "payload": row_block["payload"],
                            "start_row": current_row,
                            "start_col": start_col,
                            "span": span,
                            "data_col": data_col,
                        }
                    )
                    next_row = add_openpyxl_chart(
                        ws,
                        row_block["payload"],
                        current_row,
                        start_col=start_col,
                        width_columns=span,
                        data_col=data_col,
                    )
                    chart_index += 1
                    row_height = max(row_height, next_row - current_row)
                elif row_block["type"] == "text":
                    end_col = start_col + span - 1
                    if span > 1:
                        ws.merge_cells(
                            start_row=current_row,
                            start_column=start_col,
                            end_row=current_row,
                            end_column=end_col,
                        )
                    c = ws.cell(
                        row=current_row,
                        column=start_col,
                        value=row_block["value"],
                    )
                    c.font = _font_from_text_block(row_block)
                    c.alignment = _alignment_from_text_block(row_block)
                    _apply_row_height(ws, current_row, row_block.get("height"))
                elif row_block["type"] == "image":
                    path = _resolve_image_src(row_block["src"])
                    if path:
                        try:
                            img = XLImage(path)
                            _fit_image(img, max(120, span * 90), 80)
                            ws.add_image(
                                img, f"{get_column_letter(start_col)}{current_row}"
                            )
                            row_height = max(row_height, 2)
                        except Exception as e:  # pragma: no cover
                            logger.warning("Image insert failed: %s", e)
            current_row += row_height
            continue

        if block["type"] == "table":
            table_max_col = _write_html_table(
                ws,
                block["rows"],
                current_row,
                thin_border,
                dept_fill,
                layout_columns=layout_columns,
            )
            max_col = max(max_col, table_max_col)
            current_row += len(block["rows"])
        elif block["type"] == "chart":
            data_col = 20 + chart_index * 2
            chart_specs.append(
                {
                    "payload": block["payload"],
                    "start_row": current_row,
                    "start_col": 1,
                    "data_col": data_col,
                }
            )
            current_row = add_openpyxl_chart(
                ws, block["payload"], current_row, data_col=data_col
            )
            chart_index += 1
        elif block["type"] == "text":
            end_col = text_span or max(max_col, 1)
            if end_col > 1:
                ws.merge_cells(
                    start_row=current_row,
                    start_column=1,
                    end_row=current_row,
                    end_column=end_col,
                )
            c = ws.cell(row=current_row, column=1, value=block["value"])
            c.font = _font_from_text_block(block)
            c.alignment = _alignment_from_text_block(block)
            _apply_row_height(ws, current_row, block.get("height"))
            current_row += 1
        elif block["type"] == "image":
            path = _resolve_image_src(block["src"])
            if path:
                try:
                    img = XLImage(path)
                    _fit_image(img, 120, 40)
                    ws.add_image(img, f"A{current_row}")
                    current_row += 2
                except Exception as e:  # pragma: no cover - environment specific
                    logger.warning("Image insert failed: %s", e)
        elif block["type"] == "gap":
            current_row += max(0, int(block.get("rows") or 0))
        block_index += 1

    width_cols = layout_columns or max_col
    for ci in range(1, width_cols + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 14

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue(), chart_specs


def _write_html_table(
    ws,
    rows: list,
    start_row: int,
    thin_border,
    dept_fill,
    *,
    layout_columns: int | None = None,
    start_column: int = 1,
    strict_width: bool = False,
) -> int:
    """Write one parsed table into the worksheet; returns the max column used."""
    # Expand rowspan/colspan into a sparse grid so merge ranges are computed once.
    grid: dict[tuple[int, int], dict] = {}
    occupied: set[tuple[int, int]] = set()
    r = 0
    for tr in rows:
        c = 0
        for cell in tr:
            while (r, c) in occupied:
                c += 1
            for dr in range(cell["rowspan"]):
                for dc in range(cell["colspan"]):
                    occupied.add((r + dr, c + dc))
            grid[(r, c)] = cell
            c += cell["colspan"]
        r += 1

    natural_max = 1
    for (row_i, col_i), cell in grid.items():
        natural_max = max(natural_max, col_i + cell["colspan"])
    if strict_width and layout_columns and natural_max > layout_columns:
        raise ValueError(
            f"Bảng có {natural_max} cột logic nhưng khối report-row chỉ rộng "
            f"{layout_columns} cột."
        )

    spans: list[int] | None = None
    starts: list[int] | None = None
    if layout_columns and natural_max <= layout_columns:
        spans = _even_column_spans(natural_max, layout_columns)
        starts = []
        pos = start_column
        for span in spans:
            starts.append(pos)
            pos += span

    max_col = start_column + (layout_columns or natural_max) - 1
    applied_heights: set[int] = set()
    for (row_i, col_i), cell in grid.items():
        ws_row = start_row + row_i
        if starts is not None and spans is not None:
            ws_col = starts[col_i]
            excel_colspan = sum(spans[col_i : col_i + cell["colspan"]])
        else:
            ws_col = start_column + col_i
            excel_colspan = cell["colspan"]
        excel_rowspan = cell["rowspan"]
        max_col = max(max_col, ws_col + excel_colspan - 1)

        if cell.get("image"):
            path = _resolve_image_src(cell["image"])
            if path:
                try:
                    img = XLImage(path)
                    _fit_image(img, 240, 80)
                    ws.add_image(img, f"{get_column_letter(ws_col)}{ws_row}")
                except Exception as e:  # pragma: no cover
                    logger.warning("Image insert failed: %s", e)
            continue

        c = ws.cell(row=ws_row, column=ws_col, value=cell["text"])
        c.border = thin_border
        c.alignment = Alignment(
            vertical="center",
            wrap_text=True,
            horizontal="center" if cell["header"] else "left",
        )
        if cell["abnormal"]:
            c.font = Font(bold=True, size=DEFAULT_EXCEL_FONT_SIZE, color="CC0000")
        elif cell["header"] or cell["dept_header"]:
            c.font = Font(bold=True, size=DEFAULT_EXCEL_FONT_SIZE)
        else:
            c.font = Font(size=DEFAULT_EXCEL_FONT_SIZE)
        if cell["dept_header"]:
            c.fill = dept_fill

        if excel_colspan > 1 or excel_rowspan > 1:
            ws.merge_cells(
                start_row=ws_row,
                start_column=ws_col,
                end_row=ws_row + excel_rowspan - 1,
                end_column=ws_col + excel_colspan - 1,
            )
            for mr in range(excel_rowspan):
                for mc in range(excel_colspan):
                    if (mr, mc) == (0, 0):
                        continue
                    ws.cell(row=ws_row + mr, column=ws_col + mc).border = thin_border

    for row_i, tr in enumerate(rows):
        height = getattr(tr, "height", None)
        if height is None:
            continue
        ws_row = start_row + row_i
        if ws_row in applied_heights:
            continue
        _apply_row_height(ws, ws_row, height)
        applied_heights.add(ws_row)

    return max_col


def _render_excel_with_template(
    report, cep, exam_date: str | None
) -> tuple[bytes, str]:
    # The classic clinical detail table keeps its original Excel builder so the
    # merged R7/R8/R9/R10 header layout is preserved byte-for-byte. Other body
    # types (department_templates, summary_stats, …) render through the dynamic
    # engine and get converted from HTML.
    if report.template.body_type == report.template.BODY_CLINICAL_DETAIL_TABLE:
        return _render_clinical_detail_excel(report, cep, exam_date)

    from openpyxl import load_workbook

    from reports.render import render_report
    from reports.report_builder import build_report_dataset
    from reports.xlsx_letterhead import (
        apply_letterhead,
        media_path,
        restore_letterhead_drawings,
    )

    dataset = build_report_dataset(cep, exam_date=exam_date)
    html = render_report(report.template, dataset, report=report)

    layout_columns = None
    if report.report_type == report.REPORT_COMPANY_SUMMARY:
        layout_columns = COMPANY_SUMMARY_EXCEL_COLUMNS

    sheet_title = "Báo cáo"
    file_bytes, chart_specs = _html_document_to_excel(
        html, sheet_title=sheet_title, layout_columns=layout_columns
    )

    header_path = media_path(getattr(report.template, "header_xlsx", None))
    footer_path = media_path(getattr(report.template, "footer_xlsx", None))
    if header_path or footer_path:
        from reports.xlsx_letterhead import (
            embed_charts_preserving_drawings,
            fragment_row_count,
        )

        header_gap_rows = _parse_excel_header_gap(html)
        header_rows = fragment_row_count(header_path) if header_path else 0
        body_start = _letterhead_body_start(header_rows, header_gap_rows)
        body_row_offset = body_start - 1

        wb = load_workbook(io.BytesIO(file_bytes))
        # Header workbook is the base so logo anchors stay on original rows.
        # Body "evenness" is only via colspan stretching across the 15-col grid.
        # Charts are NOT copied here — openpyxl + restore_letterhead_drawings
        # would drop them; re-injected after restore below.
        wb = apply_letterhead(
            wb,
            header_path,
            footer_path,
            header_gap_rows=header_gap_rows,
        )
        final_sheet_title = wb.worksheets[0].title
        out = io.BytesIO()
        wb.save(out)
        file_bytes = out.getvalue()
        # Restore grouped shapes / frames that openpyxl drops on save.
        file_bytes = restore_letterhead_drawings(file_bytes, header_path)
        if not header_path:
            file_bytes = restore_letterhead_drawings(file_bytes, footer_path)

        if chart_specs:
            shifted = [
                {
                    **spec,
                    "start_row": spec["start_row"] + body_row_offset,
                }
                for spec in chart_specs
            ]
            file_bytes = embed_charts_preserving_drawings(
                file_bytes, shifted, sheet_title=final_sheet_title
            )

    return file_bytes, "xlsx"


def _render_clinical_detail_excel(
    report, cep, exam_date: str | None
) -> tuple[bytes, str]:
    """Original Excel path for the ``clinical_detail_table`` body type."""
    from reports.xlsx_letterhead import media_path

    report_data = build_clinical_detail_report(cep)
    file_bytes = _build_clinical_detail_excel(
        report_data,
        report.company.name,
        exam_date=exam_date or "",
        exam_package_name=cep.exam_package.name,
        use_clinic_header=False,
        header_xlsx=media_path(getattr(report.template, "header_xlsx", None)),
        footer_xlsx=media_path(getattr(report.template, "footer_xlsx", None)),
    )
    return file_bytes, "xlsx"


def _render_legacy_excel(report, cep, exam_date: str | None) -> tuple[bytes, str]:
    """Backwards-compatible path: the original hardcoded Excel export."""
    if report.report_type != report.REPORT_CLINICAL_DETAIL:
        raise NotImplementedError(
            f"Loại báo cáo '{report.get_report_type_display()}' cần chọn template."
        )
    if report.output_format != report.FORMAT_EXCEL:
        raise ValueError(
            "Xuất HTML yêu cầu chọn template báo cáo. "
            "Chọn định dạng Excel để dùng bộ xuất mặc định."
        )

    report_data = build_clinical_detail_report(cep)
    file_bytes = _build_clinical_detail_excel(
        report_data,
        report.company.name,
        exam_date=exam_date or "",
        exam_package_name=cep.exam_package.name,
        use_clinic_header=True,
    )
    return file_bytes, "xlsx"


def _ensure_employee_reports(
    cep: CompanyExamPackage,
    exam_date: str | None,
    created_by: Any,
) -> None:
    """Create or update per-employee exam result reports for a package."""
    from reports.models import EmployeeExamReport, ReportTemplate
    from reports.report_builder import build_report_dataset
    from reports.render import render_report

    template = ReportTemplate.objects.filter(
        name="Employee Exam Report", is_active=True
    ).first()
    if template is None:
        logger.warning("Employee Exam Report template not found — skipping")
        return

    ds = build_report_dataset(cep, exam_date=exam_date)
    exam_ids = [p.examination_id for p in ds.patients]
    existing_ids = set(
        EmployeeExamReport.objects.filter(
            examination_id__in=exam_ids, status=EmployeeExamReport.STATUS_DONE
        ).values_list("examination_id", flat=True)
    )

    created = 0
    for p in ds.patients:
        if p.examination_id in existing_ids:
            continue

        report, _ = EmployeeExamReport.objects.get_or_create(
            examination_id=p.examination_id,
            defaults={
                "template": template,
                "status": EmployeeExamReport.STATUS_PROCESSING,
                "created_by": created_by,
            },
        )
        if report.status == EmployeeExamReport.STATUS_DONE:
            continue

        # Build single-patient dataset.
        single_ds = build_report_dataset(cep, exam_date=exam_date)
        single_ds.patients = [
            sp for sp in single_ds.patients if sp.examination_id == p.examination_id
        ]
        if not single_ds.patients:
            continue

        try:
            html = render_report(template, single_ds)
            filename = (
                f"{_slugify_filename(cep.company.name)}"
                f"_{p.ma_nv}_{date.today().isoformat()}.html"
            )
            report.file.save(filename, ContentFile(html.encode("utf-8")), save=False)
            report.status = EmployeeExamReport.STATUS_DONE
            report.error_message = ""
            report.save()
            created += 1
        except Exception:
            logger.exception(
                "EmployeeExamReport failed for examination %s", p.examination_id
            )
            report.status = EmployeeExamReport.STATUS_FAILED
            report.error_message = str(Exception)
            report.save()

    if created:
        logger.info(
            "Created %d employee reports for %s / %s",
            created,
            cep.company.name,
            cep.exam_package.name,
        )


@shared_task
def generate_employee_report_task(examination_id: str) -> None:
    """
    Generate (or regenerate) a single employee exam report.

    Can be called directly or via ``_ensure_employee_reports``.
    """
    from reports.models import EmployeeExamReport, ReportTemplate
    from reports.report_builder import build_report_dataset
    from reports.render import render_report

    template = ReportTemplate.objects.filter(
        name="Employee Exam Report", is_active=True
    ).first()
    if template is None:
        return

    try:
        report = EmployeeExamReport.objects.select_related(
            "examination__company_exam_package__company",
            "examination__company_exam_package__exam_package",
        ).get(examination_id=examination_id)
    except EmployeeExamReport.DoesNotExist:
        return

    exam = report.examination
    cep = exam.company_exam_package
    if cep is None:
        report.status = EmployeeExamReport.STATUS_FAILED
        report.error_message = "Examination is not linked to a company package."
        report.save()
        return

    ds = build_report_dataset(cep, exam_date=str(exam.exam_date))
    ds.patients = [p for p in ds.patients if p.examination_id == str(exam.id)]
    if not ds.patients:
        report.status = Report.STATUS_FAILED
        report.error_message = "No data found for this examination."
        report.save()
        return

    try:
        html = render_report(template, ds)
        filename = (
            f"{_slugify_filename(cep.company.name)}"
            f"_{ds.patients[0].ma_nv}_{date.today().isoformat()}.html"
        )
        report.file.save(filename, ContentFile(html.encode("utf-8")), save=False)
        report.status = EmployeeExamReport.STATUS_DONE
        report.error_message = ""
        report.save()
    except Exception as e:
        logger.exception("EmployeeExamReport task failed for %s", examination_id)
        report.status = EmployeeExamReport.STATUS_FAILED
        report.error_message = str(e)
        report.save()
