"""
Copy static Excel letterhead fragments (header/footer) into a report workbook.

Uploaded ``.xlsx`` files are treated as static branding blocks: cells, styles,
merged ranges, row heights, and images are copied as-is (no placeholder
substitution).

When a header file is present, that workbook becomes the base sheet so native
drawings (TwoCellAnchor logos/frames) are never re-encoded. The generated body
is appended below it.
"""

from __future__ import annotations

import copy
import io
import logging
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from openpyxl import Workbook, load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.drawing.spreadsheet_drawing import (
    AbsoluteAnchor,
    AnchorMarker,
    OneCellAnchor,
    TwoCellAnchor,
)
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

logger = logging.getLogger(__name__)


def _used_bounds(ws: Worksheet) -> tuple[int, int, int, int]:
    """Return (min_row, max_row, min_col, max_col) covering values, merges, images."""
    min_row: int | None = None
    max_row = 0
    min_col: int | None = None
    max_col = 0

    def _expand(r: int, c: int) -> None:
        nonlocal min_row, max_row, min_col, max_col
        min_row = r if min_row is None else min(min_row, r)
        max_row = max(max_row, r)
        min_col = c if min_col is None else min(min_col, c)
        max_col = max(max_col, c)

    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                _expand(cell.row, cell.column)
                continue
            fill = cell.fill
            if fill and fill.fill_type and fill.fill_type != "none":
                _expand(cell.row, cell.column)

    for merged in ws.merged_cells.ranges:
        _expand(merged.min_row, merged.min_col)
        _expand(merged.max_row, merged.max_col)

    for img in getattr(ws, "_images", []) or []:
        for r, c in _anchor_cells(img.anchor):
            _expand(r, c)

    if min_row is None or min_col is None:
        return 1, 0, 1, 0
    return min_row, max_row, min_col, max_col


def _anchor_cells(anchor: Any) -> list[tuple[int, int]]:
    """Excel 1-based (row, col) cells touched by an image anchor."""
    cells: list[tuple[int, int]] = []
    if anchor is None:
        return cells
    _from = getattr(anchor, "_from", None) or getattr(anchor, "from", None)
    if _from is not None:
        try:
            cells.append((int(_from.row) + 1, int(_from.col) + 1))
        except Exception:
            logger.debug("Could not read image anchor from-marker", exc_info=True)
    _to = getattr(anchor, "to", None)
    if _to is not None:
        try:
            cells.append((int(_to.row) + 1, int(_to.col) + 1))
        except Exception:
            logger.debug("Could not read image anchor to-marker", exc_info=True)
    return cells


def _copy_cell_style(source: Any, target: Any) -> None:
    """Copy openpyxl style attributes from ``source`` onto ``target``."""
    if source.has_style:
        target.font = copy.copy(source.font)
        target.border = copy.copy(source.border)
        target.fill = copy.copy(source.fill)
        target.number_format = source.number_format
        target.protection = copy.copy(source.protection)
        target.alignment = copy.copy(source.alignment)


def copy_sheet_fragment(
    src_ws: Worksheet,
    dest_ws: Worksheet,
    dest_start_row: int = 1,
    *,
    dest_start_col: int = 1,
    prefer_source_widths: bool = False,
    copy_widths: bool = True,
    copy_images: bool = True,
) -> int:
    """
    Copy the used range of ``src_ws`` into ``dest_ws`` starting at
    ``dest_start_row``.

    When ``prefer_source_widths`` is True (letterhead), destination column
    widths are overwritten from the source so uploaded header/footer layout
    is preserved even if the body sheet already set equal widths.

    Returns the number of rows occupied by the fragment (0 if empty).
    """
    min_row, max_row, min_col, max_col = _used_bounds(src_ws)
    if max_row < min_row:
        return 0

    row_offset = dest_start_row - min_row
    col_offset = dest_start_col - min_col

    for r in range(min_row, max_row + 1):
        src_height = src_ws.row_dimensions[r].height
        dest_r = r + row_offset
        if src_height is not None:
            dest_ws.row_dimensions[dest_r].height = src_height
        for c in range(min_col, max_col + 1):
            src_cell = src_ws.cell(row=r, column=c)
            dest_cell = dest_ws.cell(row=dest_r, column=c + col_offset)
            dest_cell.value = src_cell.value
            _copy_cell_style(src_cell, dest_cell)

    if copy_widths:
        for col in range(min_col, max_col + 1):
            letter = get_column_letter(col)
            dest_letter = get_column_letter(col + col_offset)
            width = src_ws.column_dimensions[letter].width
            if width is None and prefer_source_widths:
                width = src_ws.sheet_format.defaultColWidth
            if width is not None:
                existing = dest_ws.column_dimensions[dest_letter].width
                if prefer_source_widths or existing is None or width > existing:
                    dest_ws.column_dimensions[dest_letter].width = width

    for merged in list(src_ws.merged_cells.ranges):
        min_r, min_c, max_r, max_c = (
            merged.min_row,
            merged.min_col,
            merged.max_row,
            merged.max_col,
        )
        dest_ws.merge_cells(
            start_row=min_r + row_offset,
            start_column=min_c + col_offset,
            end_row=max_r + row_offset,
            end_column=max_c + col_offset,
        )

    if copy_images:
        _copy_images(src_ws, dest_ws, row_offset=row_offset, col_offset=col_offset)

    return max_row - min_row + 1


def _shift_marker(marker: Any, *, row_offset: int, col_offset: int) -> AnchorMarker:
    return AnchorMarker(
        col=int(getattr(marker, "col", 0)) + col_offset,
        colOff=int(getattr(marker, "colOff", 0) or 0),
        row=int(getattr(marker, "row", 0)) + row_offset,
        rowOff=int(getattr(marker, "rowOff", 0) or 0),
    )


def _copy_images(
    src_ws: Worksheet,
    dest_ws: Worksheet,
    *,
    row_offset: int,
    col_offset: int,
) -> None:
    """Copy worksheet images, preserving TwoCellAnchor / OneCellAnchor sizing."""
    for img in list(getattr(src_ws, "_images", []) or []):
        try:
            data = getattr(img, "_data", None)
            if callable(data):
                blob = data()
            else:
                blob = getattr(img, "ref", None)
            if blob is None:
                continue
            if isinstance(blob, (bytes, bytearray)):
                stream = io.BytesIO(blob)
            else:
                stream = blob
            new_img = XLImage(stream)
            if getattr(img, "width", None):
                new_img.width = img.width
            if getattr(img, "height", None):
                new_img.height = img.height

            anchor = getattr(img, "anchor", None)
            if isinstance(anchor, TwoCellAnchor):
                new_img.anchor = TwoCellAnchor(
                    _from=_shift_marker(
                        anchor._from, row_offset=row_offset, col_offset=col_offset
                    ),
                    to=_shift_marker(
                        anchor.to, row_offset=row_offset, col_offset=col_offset
                    ),
                )
                if getattr(anchor, "editAs", None) is not None:
                    new_img.anchor.editAs = anchor.editAs
                dest_ws.add_image(new_img)
            elif isinstance(anchor, OneCellAnchor):
                new_anchor = OneCellAnchor(
                    _from=_shift_marker(
                        anchor._from, row_offset=row_offset, col_offset=col_offset
                    ),
                    ext=copy.copy(anchor.ext) if getattr(anchor, "ext", None) else None,
                )
                if getattr(anchor, "editAs", None) is not None:
                    new_anchor.editAs = anchor.editAs
                new_img.anchor = new_anchor
                dest_ws.add_image(new_img)
            elif isinstance(anchor, AbsoluteAnchor):
                # Rare for letterheads; fall back to pixel size at origin.
                dest_ws.add_image(new_img)
            else:
                # String / unknown anchors — keep previous best-effort placement.
                _from = getattr(anchor, "_from", None) or getattr(anchor, "from", None)
                if _from is not None:
                    col = int(getattr(_from, "col", 0)) + col_offset
                    row = int(getattr(_from, "row", 0)) + row_offset
                    cell = f"{get_column_letter(col + 1)}{row + 1}"
                    dest_ws.add_image(new_img, cell)
                else:
                    dest_ws.add_image(new_img)
        except Exception:
            logger.warning("Failed to copy letterhead image", exc_info=True)


def _load_first_sheet(path: str | Path) -> tuple[Any, Worksheet]:
    wb = load_workbook(str(path))
    return wb, wb.worksheets[0]


def fragment_row_count(path: str | Path | None) -> int:
    """Return how many rows a letterhead file occupies (0 if missing/empty)."""
    if not path:
        return 0
    p = Path(str(path))
    if not p.is_file():
        return 0
    try:
        _wb, ws = _load_first_sheet(p)
        _min_r, max_r, _min_c, _max_c = _used_bounds(ws)
        if max_r < 1:
            return 0
        return max_r  # assume letterheads start at row 1
    except Exception:
        logger.warning("Cannot read letterhead row count from %s", path, exc_info=True)
        return 0


def _last_used_row(ws: Worksheet) -> int:
    last_used = 0
    max_row = ws.max_row or 1
    max_col = ws.max_column or 1
    for row in ws.iter_rows(min_row=1, max_row=max_row, max_col=max_col):
        if any(c.value is not None for c in row):
            last_used = row[0].row
    # Images may extend below the last value cell.
    for img in getattr(ws, "_images", []) or []:
        for r, _c in _anchor_cells(img.anchor):
            last_used = max(last_used, r)
    return last_used


def apply_letterhead(
    wb: Workbook,
    header_path: str | Path | None = None,
    footer_path: str | Path | None = None,
    *,
    sheet_index: int = 0,
    header_gap_rows: int = 1,
) -> Workbook:
    """
    Merge uploaded header/footer into the report workbook.

    When ``header_path`` is set, the header workbook is used as the base sheet
    so logos/frames keep their native TwoCellAnchor sizing. Body cells are
    appended below; footer is appended after that (images re-copied carefully).

    ``header_gap_rows`` is the number of blank rows between the last header
    cell row and the first body row (default ``1``, matching the historical
    ``header_rows + 2`` placement).
    """
    body_ws = wb.worksheets[sheet_index]
    header_ok = bool(header_path and Path(str(header_path)).is_file())
    footer_ok = bool(footer_path and Path(str(footer_path)).is_file())
    gap = max(0, int(header_gap_rows))

    had_header = False
    if header_ok:
        try:
            base_wb, base_ws = _load_first_sheet(header_path)
            _h_min, h_max, _h_min_c, _h_max_c = _used_bounds(base_ws)
            header_rows = max(0, h_max) if h_max >= 1 else 0
            body_start = header_rows + 1 + gap if header_rows else 1
            # Append generated body under the intact header (no width/image clobber).
            copy_sheet_fragment(
                body_ws,
                base_ws,
                dest_start_row=body_start,
                copy_widths=False,
                copy_images=True,
            )
            wb = base_wb
            had_header = header_rows > 0
        except Exception:
            logger.exception("Failed to apply header letterhead from %s", header_path)

    ws = wb.worksheets[0]

    if footer_ok:
        try:
            _fwb, footer_ws = _load_first_sheet(footer_path)
            start = _last_used_row(ws) + 2
            copy_sheet_fragment(
                footer_ws,
                ws,
                dest_start_row=start,
                prefer_source_widths=not had_header,
                copy_widths=not had_header,
            )
            if not had_header:
                _copy_column_widths(footer_ws, ws)
        except Exception:
            logger.exception("Failed to apply footer letterhead from %s", footer_path)

    return wb


def _copy_column_widths(src_ws: Worksheet, dest_ws: Worksheet) -> None:
    """Overwrite destination column widths from ``src_ws`` (letterhead exact)."""
    for letter, dim in src_ws.column_dimensions.items():
        if dim.width is not None:
            dest_ws.column_dimensions[letter].width = dim.width


def media_path(file_field: Any) -> str | None:
    """Return a filesystem path for a Django FileField, or None."""
    if not file_field:
        return None
    try:
        path = file_field.path
    except Exception:
        return None
    return path if path and Path(path).is_file() else None


# Parts openpyxl drops on save (grouped frames live in drawing XML).
_DRAWING_PREFIXES = (
    "xl/drawings/",
    "xl/media/",
)


def restore_letterhead_drawings(
    workbook_bytes: bytes,
    letterhead_path: str | Path | None,
) -> bytes:
    """
    Re-inject native drawing/media parts from an uploaded letterhead.

    openpyxl only round-trips ``_images`` (one ``<pic>``). Grouped shapes that
    form frames (``grpSp``) live in the original ``drawing1.xml`` and are
    stripped on save — this restores them.

    Only ``xl/drawings/*`` and ``xl/media/*`` are replaced. Sheet XML / styles /
    theme are left untouched so fonts and alignment stay intact. openpyxl also
    drops the sheet→drawing relationship on save, so this re-attaches
    ``drawing1.xml`` to the worksheet afterwards.
    """
    import zipfile

    if not letterhead_path:
        return workbook_bytes
    src_path = Path(str(letterhead_path))
    if not src_path.is_file():
        return workbook_bytes

    try:
        with zipfile.ZipFile(src_path) as src_zip:
            restore_names = [
                name
                for name in src_zip.namelist()
                if name.startswith(_DRAWING_PREFIXES)
                # VML/ctrlProps need sheet hooks with namespaces; skip — the
                # decorative frame is in drawing1.xml group shapes, not VML.
                and not name.endswith(".vml") and "/vmlDrawing" not in name
            ]
            if not restore_names:
                return workbook_bytes
            # Prefer the SpreadsheetML drawing + its rels + media images.
            restore_blobs = {
                name: src_zip.read(name)
                for name in restore_names
                if name.endswith(".xml")
                or name.endswith(".rels")
                or name.startswith("xl/media/")
            }
            if "xl/drawings/drawing1.xml" not in restore_blobs:
                return workbook_bytes

        out_buf = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as dst_zip:
            with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as out:
                for info in dst_zip.infolist():
                    name = info.filename
                    if name in restore_blobs:
                        continue
                    # Drop openpyxl's thin drawing so the restored one wins.
                    if name.startswith("xl/drawings/") or (
                        name.startswith("xl/media/") and name in restore_blobs
                    ):
                        continue
                    out.writestr(info, dst_zip.read(name))

                for name, blob in restore_blobs.items():
                    out.writestr(name, blob)

        return _relink_restored_drawing(out_buf.getvalue())
    except Exception:
        logger.exception(
            "Failed to restore letterhead drawings from %s", letterhead_path
        )
        return workbook_bytes


def _zip_read(zf: Any, name: str) -> bytes | None:
    try:
        return zf.read(name)
    except KeyError:
        return None


_DRAWING_CT = "application/vnd.openxmlformats-officedocument.drawing+xml"
_DRAWING_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
)


def _first_worksheet_path(zf: Any) -> str | None:
    """Return ``xl/worksheets/sheetN.xml`` for the workbook's first sheet."""
    import re

    rels = _zip_read(zf, "xl/_rels/workbook.xml.rels")
    if rels:
        text = rels.decode("utf-8")
        matches = re.findall(
            r'Type="[^"]*worksheet"[^>]*Target="([^"]+)"'
            r'|Target="([^"]+)"[^>]*Type="[^"]*worksheet"',
            text,
        )
        for left, right in matches:
            target = (left or right).lstrip("/")
            if target.startswith("xl/"):
                return target
            if target.startswith("worksheets/"):
                return "xl/" + target
            return "xl/" + target
    names = [
        name
        for name in zf.namelist()
        if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
    ]
    return names[0] if names else None


def _sheet_rels_path(sheet_path: str) -> str:
    parent, name = sheet_path.rsplit("/", 1)
    return f"{parent}/_rels/{name}.rels"


def _relink_restored_drawing(workbook_bytes: bytes) -> bytes:
    """
    Re-attach ``drawing1.xml`` to the worksheet after openpyxl dropped the link.

    Restoring drawing parts is not enough: Excel only renders them when the
    sheet has ``<drawing r:id="…"/>`` and a matching relationship. openpyxl
    strips both on save because it cannot round-trip grouped letterhead shapes.
    """
    import re
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as zf:
            names = set(zf.namelist())
            if "xl/drawings/drawing1.xml" not in names:
                return workbook_bytes
            sheet_path = _first_worksheet_path(zf)
            if not sheet_path:
                return workbook_bytes
            sheet_xml = _zip_read(zf, sheet_path)
            ct_xml = _zip_read(zf, "[Content_Types].xml")
            if sheet_xml is None or ct_xml is None:
                return workbook_bytes

            rels_path = _sheet_rels_path(sheet_path)
            rels_xml = _zip_read(zf, rels_path)

            ct_text = ct_xml.decode("utf-8")
            drawing_override = (
                '<Override PartName="/xl/drawings/drawing1.xml" '
                f'ContentType="{_DRAWING_CT}"/>'
            )
            if "/xl/drawings/drawing1.xml" not in ct_text:
                if "</Types>" not in ct_text:
                    return workbook_bytes
                ct_text = ct_text.replace("</Types>", drawing_override + "</Types>", 1)
            if (
                any(
                    name.startswith("xl/media/")
                    and name.lower().endswith((".jpeg", ".jpg"))
                    for name in names
                )
                and 'Extension="jpeg"' not in ct_text
            ):
                ct_text = re.sub(
                    r"(<Types\b[^>]*>)",
                    r'\1<Default Extension="jpeg" ContentType="image/jpeg"/>',
                    ct_text,
                    count=1,
                )
            if (
                any(
                    name.startswith("xl/media/") and name.lower().endswith(".png")
                    for name in names
                )
                and 'Extension="png"' not in ct_text
            ):
                ct_text = re.sub(
                    r"(<Types\b[^>]*>)",
                    r'\1<Default Extension="png" ContentType="image/png"/>',
                    ct_text,
                    count=1,
                )

            if rels_xml:
                rels_text = rels_xml.decode("utf-8")
            else:
                rels_text = (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    f'<Relationships xmlns="{_REL_NS}"></Relationships>'
                )
            if "relationships/drawing" not in rels_text:
                rid_nums = [int(x) for x in re.findall(r'Id="rId(\d+)"', rels_text)]
                rid = f"rId{(max(rid_nums) + 1) if rid_nums else 1}"
                if "</Relationships>" not in rels_text:
                    return workbook_bytes
                rels_text = rels_text.replace(
                    "</Relationships>",
                    f'<Relationship Id="{rid}" Type="{_DRAWING_REL_TYPE}" '
                    'Target="../drawings/drawing1.xml"/></Relationships>',
                    1,
                )
            else:
                rid_match = re.search(
                    r'Id="(rId\d+)"[^>]*Type="[^"]*drawing"'
                    r'|Type="[^"]*drawing"[^>]*Id="(rId\d+)"',
                    rels_text,
                )
                rid = (
                    (rid_match.group(1) or rid_match.group(2)) if rid_match else "rId1"
                )

            sheet_text = sheet_xml.decode("utf-8")
            if "xmlns:r=" not in sheet_text:
                sheet_text = re.sub(
                    r"(<worksheet\b)",
                    rf'\1 xmlns:r="{_R_NS}"',
                    sheet_text,
                    count=1,
                )
            if "<drawing" not in sheet_text:
                if "</worksheet>" not in sheet_text:
                    return workbook_bytes
                sheet_text = sheet_text.replace(
                    "</worksheet>",
                    f'<drawing r:id="{rid}"/></worksheet>',
                    1,
                )

            out_buf = io.BytesIO()
            with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as out:
                for info in zf.infolist():
                    name = info.filename
                    if name == sheet_path:
                        out.writestr(info, sheet_text.encode("utf-8"))
                    elif name == rels_path:
                        out.writestr(info, rels_text.encode("utf-8"))
                    elif name == "[Content_Types].xml":
                        out.writestr(info, ct_text.encode("utf-8"))
                    else:
                        out.writestr(info, zf.read(name))
                if rels_path not in names:
                    out.writestr(rels_path, rels_text.encode("utf-8"))
            return out_buf.getvalue()
    except Exception:
        logger.exception("Failed to relink restored letterhead drawing")
        return workbook_bytes


_CHART_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_XDR_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_CHART_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
)
_CHART_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"
)

# SpreadsheetDrawing element local names that letterheads prefix with ``xdr:``.
# Includes from/to children (col, row, …): omitting those leaves mixed-namespace
# XML that Excel silently drops, so charts never appear on the sheet.
_XDR_LOCAL_TAGS = (
    "oneCellAnchor",
    "twoCellAnchor",
    "absoluteAnchor",
    "from",
    "to",
    "ext",
    "graphicFrame",
    "nvGraphicFramePr",
    "cNvPr",
    "cNvGraphicFramePr",
    "xfrm",
    "clientData",
    "col",
    "colOff",
    "row",
    "rowOff",
)


def _prefix_xdr_fragment(fragment: str) -> str:
    """Rewrite openpyxl's default-ns drawing fragment to ``xdr:`` prefixes."""
    out = fragment
    for tag in _XDR_LOCAL_TAGS:
        out = out.replace(f"<{tag}>", f"<xdr:{tag}>")
        out = out.replace(f"<{tag} ", f"<xdr:{tag} ")
        out = out.replace(f"</{tag}>", f"</xdr:{tag}>")
        out = out.replace(f"<{tag}/>", f"<xdr:{tag}/>")
    return out


def _retarget_anchor_ids(fragment: str, new_rid: str, shape_id: int) -> str:
    """Point a scratch chart anchor at ``new_rid`` / ``shape_id``."""
    import re

    frag = re.sub(r'r:id="rId\d+"', f'r:id="{new_rid}"', fragment, count=1)
    return re.sub(
        r'(<(?:xdr:)?cNvPr\b[^>]*\bid=")(\d+)(")',
        rf"\g<1>{shape_id}\3",
        frag,
        count=1,
    )


def _rewrite_chart_anchor(
    fragment: str,
    *,
    uses_xdr: bool,
    new_rid: str,
    shape_id: int,
) -> str:
    """
    Adapt an openpyxl chart anchor so Excel will display it on a letterhead sheet.

    openpyxl serializes SpreadsheetDrawing in the default namespace (``<from>``,
    ``<col>``). Uploaded letterheads use the ``xdr:`` prefix. Prefixing only the
    parent tags left ``<xdr:from><col>`` — invalid OOXML that Excel ignores.
    """
    if not uses_xdr:
        return _retarget_anchor_ids(fragment, new_rid, shape_id)

    wrapper = (
        f'<wsDr xmlns="{_XDR_NS}" xmlns:a="{_A_NS}" '
        f'xmlns:c="{_CHART_NS}" xmlns:r="{_R_NS}">'
        f"{fragment}</wsDr>"
    )
    try:
        ET.register_namespace("xdr", _XDR_NS)
        ET.register_namespace("a", _A_NS)
        ET.register_namespace("c", _CHART_NS)
        ET.register_namespace("r", _R_NS)
        root = ET.fromstring(wrapper)
        anchor = list(root)[0]
        rid_attr = f"{{{_R_NS}}}id"
        for el in anchor.iter():
            if rid_attr in el.attrib:
                el.attrib[rid_attr] = new_rid
            if el.tag == f"{{{_XDR_NS}}}cNvPr":
                el.attrib["id"] = str(shape_id)
        for el in anchor.iter(f"{{{_XDR_NS}}}xfrm"):
            if len(list(el)) == 0:
                off = ET.SubElement(el, f"{{{_A_NS}}}off")
                off.set("x", "0")
                off.set("y", "0")
                ext = ET.SubElement(el, f"{{{_A_NS}}}ext")
                ext.set("cx", "0")
                ext.set("cy", "0")
        return ET.tostring(anchor, encoding="unicode")
    except ET.ParseError:
        logger.warning("Chart anchor XML parse failed; falling back to string prefix")
        return _prefix_xdr_fragment(_retarget_anchor_ids(fragment, new_rid, shape_id))


def _embed_charts_via_openpyxl(
    workbook_bytes: bytes,
    chart_specs: list[dict[str, Any]],
    sheet_title: str,
) -> bytes:
    """Add charts with openpyxl when the destination has no drawing to preserve."""
    from reports.charts import add_openpyxl_chart

    wb = load_workbook(io.BytesIO(workbook_bytes))
    ws = wb.worksheets[0]
    if sheet_title:
        for candidate in wb.worksheets:
            if candidate.title == sheet_title:
                ws = candidate
                break
    for spec in chart_specs:
        add_openpyxl_chart(
            ws,
            spec.get("payload") or {},
            int(spec.get("start_row") or 1),
            start_col=int(spec.get("start_col") or 1),
            width_columns=spec.get("span"),
            data_col=int(spec.get("data_col") or 20),
        )
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def embed_charts_preserving_drawings(
    workbook_bytes: bytes,
    chart_specs: list[dict[str, Any]],
    *,
    sheet_title: str,
) -> bytes:
    """
    Inject native Excel charts into a workbook that already has letterhead drawings.

    ``restore_letterhead_drawings`` replaces ``xl/drawings/*``, which strips any
    charts openpyxl wrote earlier. This rebuilds chart parts in a scratch
    workbook and merges their anchors/rels into the existing drawing XML so
    letterhead frames/logos stay intact.
    """
    import re
    import zipfile

    from reports.charts import add_openpyxl_chart

    if not chart_specs:
        return workbook_bytes

    workbook_bytes = _relink_restored_drawing(workbook_bytes)

    scratch = Workbook()
    sws = scratch.active
    sws.title = (sheet_title or "Sheet1")[:31]
    for spec in chart_specs:
        payload = spec.get("payload") or {}
        start_row = int(spec.get("start_row") or 1)
        add_openpyxl_chart(
            sws,
            payload,
            start_row,
            start_col=int(spec.get("start_col") or 1),
            width_columns=spec.get("span"),
            data_col=int(spec.get("data_col") or 20),
        )

    scratch_buf = io.BytesIO()
    scratch.save(scratch_buf)
    scratch_bytes = scratch_buf.getvalue()

    try:
        with zipfile.ZipFile(io.BytesIO(scratch_bytes)) as scratch_zip:
            scratch_drawing = _zip_read(scratch_zip, "xl/drawings/drawing1.xml")
            scratch_rels = _zip_read(scratch_zip, "xl/drawings/_rels/drawing1.xml.rels")
            chart_files = {
                name: scratch_zip.read(name)
                for name in scratch_zip.namelist()
                if name.startswith("xl/charts/") and name.endswith(".xml")
            }
            if not scratch_drawing or not chart_files:
                return workbook_bytes

            anchors = re.findall(
                r"<(?:xdr:)?oneCellAnchor\b[^>]*>.*?</(?:xdr:)?oneCellAnchor>",
                scratch_drawing.decode("utf-8"),
                flags=re.DOTALL,
            )
            if not anchors:
                logger.warning("Scratch workbook has charts but no oneCellAnchor")
                return workbook_bytes

            # Map scratch rId → chart part path from scratch rels.
            scratch_rid_to_target: dict[str, str] = {}
            if scratch_rels:
                for rid, target in re.findall(
                    r'Id="(rId\d+)"[^>]*Target="([^"]+)"',
                    scratch_rels.decode("utf-8"),
                ):
                    scratch_rid_to_target[rid] = target
                if not scratch_rid_to_target:
                    for target, rid in re.findall(
                        r'Target="([^"]+)"[^>]*Id="(rId\d+)"',
                        scratch_rels.decode("utf-8"),
                    ):
                        scratch_rid_to_target[rid] = target

        with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as dst_zip:
            dst_names = set(dst_zip.namelist())
            drawing_xml = _zip_read(dst_zip, "xl/drawings/drawing1.xml")
            drawing_rels = _zip_read(dst_zip, "xl/drawings/_rels/drawing1.xml.rels")
            content_types = _zip_read(dst_zip, "[Content_Types].xml")
            if drawing_xml is None:
                logger.info("No letterhead drawing present; adding charts via openpyxl")
                return _embed_charts_via_openpyxl(
                    workbook_bytes, chart_specs, sheet_title
                )
            if content_types is None:
                logger.warning("Cannot embed charts: missing Content_Types")
                return workbook_bytes

            drawing_text = drawing_xml.decode("utf-8")
            rels_text = (
                drawing_rels.decode("utf-8")
                if drawing_rels
                else (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    f'<Relationships xmlns="{_REL_NS}"></Relationships>'
                )
            )

            # Next free shape id / relationship id.
            shape_ids = [int(x) for x in re.findall(r'\bid="(\d+)"', drawing_text)]
            next_shape_id = (max(shape_ids) + 1) if shape_ids else 1
            rid_nums = [int(x) for x in re.findall(r'\bId="rId(\d+)"', rels_text)]
            next_rid = (max(rid_nums) + 1) if rid_nums else 1

            # Avoid colliding with any existing chart part names.
            existing_chart_nums = [
                int(m.group(1))
                for name in dst_names
                for m in [re.match(r"xl/charts/chart(\d+)\.xml", name)]
                if m
            ]
            next_chart_num = (
                (max(existing_chart_nums) + 1) if existing_chart_nums else 1
            )

            if "xmlns:c=" not in drawing_text:
                drawing_text = re.sub(
                    r"(<(?:xdr:)?wsDr\b)",
                    rf'\1 xmlns:c="{_CHART_NS}"',
                    drawing_text,
                    count=1,
                )

            uses_xdr = "<xdr:wsDr" in drawing_text or "xdr:wsDr" in drawing_text
            new_anchors: list[str] = []
            new_rels: list[str] = []
            new_chart_parts: dict[str, bytes] = {}
            new_overrides: list[str] = []

            for anchor in anchors:
                rid_match = re.search(r'r:id="(rId\d+)"', anchor)
                if not rid_match:
                    continue
                old_rid = rid_match.group(1)
                target = scratch_rid_to_target.get(old_rid)
                if not target:
                    continue
                # Normalize target to xl/charts/chartN.xml
                chart_name = target.lstrip("/")
                if chart_name.startswith("../charts/"):
                    chart_name = "xl/charts/" + chart_name.split("/")[-1]
                elif chart_name.startswith("charts/"):
                    chart_name = "xl/" + chart_name
                if chart_name not in chart_files:
                    # Try basename match
                    base = chart_name.split("/")[-1]
                    matched = next(
                        (k for k in chart_files if k.endswith("/" + base)), None
                    )
                    if not matched:
                        continue
                    chart_blob = chart_files[matched]
                else:
                    chart_blob = chart_files[chart_name]

                new_chart_path = f"xl/charts/chart{next_chart_num}.xml"
                next_chart_num += 1
                new_rid = f"rId{next_rid}"
                next_rid += 1

                frag = _rewrite_chart_anchor(
                    anchor,
                    uses_xdr=uses_xdr,
                    new_rid=new_rid,
                    shape_id=next_shape_id,
                )
                next_shape_id += 1

                new_anchors.append(frag)
                # Rel target: from drawings/ to charts/ → ../charts/chartN.xml
                rel_target = f"../charts/{new_chart_path.split('/')[-1]}"
                new_rels.append(
                    f'<Relationship Id="{new_rid}" Type="{_CHART_REL_TYPE}" '
                    f'Target="{rel_target}"/>'
                )
                new_chart_parts[new_chart_path] = chart_blob
                new_overrides.append(
                    f'<Override PartName="/{new_chart_path}" '
                    f'ContentType="{_CHART_CONTENT_TYPE}"/>'
                )

            if not new_anchors:
                return workbook_bytes

            close_tag = "</xdr:wsDr>" if uses_xdr else "</wsDr>"
            if close_tag not in drawing_text:
                logger.warning("drawing1.xml missing closing %s", close_tag)
                return workbook_bytes
            drawing_text = drawing_text.replace(
                close_tag, "".join(new_anchors) + close_tag, 1
            )

            if "</Relationships>" not in rels_text:
                logger.warning("drawing rels missing </Relationships>")
                return workbook_bytes
            rels_text = rels_text.replace(
                "</Relationships>", "".join(new_rels) + "</Relationships>", 1
            )

            ct_text = content_types.decode("utf-8")
            if "</Types>" not in ct_text:
                return workbook_bytes
            # Skip overrides that already exist.
            for override in new_overrides:
                if override not in ct_text:
                    ct_text = ct_text.replace("</Types>", override + "</Types>", 1)

            out_buf = io.BytesIO()
            with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as out:
                for info in dst_zip.infolist():
                    name = info.filename
                    if name == "xl/drawings/drawing1.xml":
                        out.writestr(info, drawing_text.encode("utf-8"))
                    elif name == "xl/drawings/_rels/drawing1.xml.rels":
                        out.writestr(info, rels_text.encode("utf-8"))
                    elif name == "[Content_Types].xml":
                        out.writestr(info, ct_text.encode("utf-8"))
                    else:
                        out.writestr(info, dst_zip.read(name))

                if "xl/drawings/_rels/drawing1.xml.rels" not in dst_names:
                    out.writestr(
                        "xl/drawings/_rels/drawing1.xml.rels",
                        rels_text.encode("utf-8"),
                    )

                for path, blob in new_chart_parts.items():
                    out.writestr(path, blob)

            return out_buf.getvalue()
    except Exception:
        logger.exception("Failed to embed charts while preserving letterhead drawings")
        return workbook_bytes
