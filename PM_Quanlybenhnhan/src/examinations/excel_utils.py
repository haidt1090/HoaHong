"""
Excel utilities for per-department template download and import — Sprint 6.

Provides:
- ``generate_department_template``: creates a blank .xlsx with headers from
  a DepartmentTemplate's fields_config.
- ``parse_department_import``: reads an uploaded .xlsx, maps columns to
  fields_config keys, and yields row dicts for processing.
"""

from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook, load_workbook

from examinations.models import is_blank_value
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation


def generate_department_template(
    department_name: str,
    fields_config: list[dict[str, Any]],
) -> bytes:
    """
    Generate a blank Excel template for a department.

    Layout:
    - Row 1: field keys (machine-readable, used for import mapping)
    - Row 2: Vietnamese labels (human reference)
    - Row 3: units (if any)
    - Row 4: normal ranges (if any)
    - Row 5+: empty, ready for data entry

    The first column is always ``employee_code`` (Mã nhân viên) to match
    patients during import.

    Returns the .xlsx file as bytes.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = department_name[:31]  # Excel sheet name limit

    # Header styling
    header_fill = PatternFill(
        start_color="4472C4", end_color="4472C4", fill_type="solid"
    )
    header_font = Font(bold=True, color="FFFFFF")

    # Column A: employee_code (required for import)
    ws.cell(row=1, column=1, value="employee_code").fill = header_fill
    ws.cell(row=1, column=1).font = header_font
    ws.cell(row=2, column=1, value="Mã nhân viên")
    ws.cell(row=3, column=1, value="")
    ws.cell(row=4, column=1, value="")

    # Remaining columns from fields_config
    for idx, field in enumerate(fields_config, start=2):
        key = field.get("key", f"field_{idx}")
        label = field.get("label", key)
        unit = field.get("unit", "")
        normal_range = field.get("normal_range")

        # Row 1: key
        cell = ws.cell(row=1, column=idx, value=key)
        cell.fill = header_fill
        cell.font = header_font

        # Row 2: label
        ws.cell(row=2, column=idx, value=label)

        # Row 3: unit
        if unit:
            ws.cell(row=3, column=idx, value=f"({unit})")

        # Row 4: normal range
        if normal_range:
            if isinstance(normal_range, dict):
                min_val = normal_range.get("min", "")
                max_val = normal_range.get("max", "")
                range_str = f"{min_val}-{max_val}" if min_val or max_val else ""
                if range_str:
                    ws.cell(row=4, column=idx, value=range_str)

        # Data validation for select/multi_select fields
        field_type = field.get("type")
        if field_type in {"select", "multi_select"}:
            options = field.get("options", [])
            if options:
                # Excel data validation requires comma-separated list
                options_str = ",".join(str(o) for o in options)
                dv = DataValidation(
                    type="list",
                    formula1=f'"{options_str}"',
                    allow_blank=True,
                )
                dv.error = "Giá trị không hợp lệ"
                dv.errorTitle = "Lỗi"
                ws.add_data_validation(dv)
                # Apply to column (rows 5-1000 as example)
                col_letter = get_column_letter(idx)
                dv.add(f"{col_letter}5:{col_letter}1000")

        # Number format for numeric fields
        if field_type == "number":
            col_letter = get_column_letter(idx)
            for row in range(5, 1001):
                ws[f"{col_letter}{row}"].number_format = "0.00"

    # Auto-adjust column widths (approximate)
    for col_idx in range(1, len(fields_config) + 2):
        col_letter = get_column_letter(col_idx)
        # Estimate width from header + sample data
        max_len = 15
        for row in range(1, 5):
            cell_value = ws.cell(row=row, column=col_idx).value
            if cell_value:
                max_len = max(max_len, len(str(cell_value)))
        ws.column_dimensions[col_letter].width = min(max_len + 2, 50)

    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def generate_department_export(
    fields_config: list[dict[str, Any]],
    employees: list[dict[str, Any]],
    sheet_name: str = "Export",
) -> bytes:
    """
    Generate a pre-populated Excel export for a company's employees.

    Layout:
    - Row 1: ``Mã NV``, ``Họ tên``, then Vietnamese field labels
    - Row 2: units (empty for the first two columns)
    - Row 3+: one row per employee, with existing exam values pre-filled

    No normal range row is included — the file contains only exam results.

    Args:
        fields_config: the department template's field definitions
        employees: list of dicts, each with ``employee_code``, ``full_name``
            and an optional ``data`` dict mapping field_key → value
        sheet_name: worksheet title

    Columns A-B (Mã NV, Họ tên) are protected (read-only). Returns .xlsx bytes.
    """
    from openpyxl.worksheet.protection import SheetProtection

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]

    header_fill = PatternFill(
        start_color="4472C4", end_color="4472C4", fill_type="solid"
    )
    header_font = Font(bold=True, color="FFFFFF")
    locked_fill = PatternFill(
        start_color="D9D9D9", end_color="D9D9D9", fill_type="solid"
    )

    # Fixed columns A, B
    for col, label in ((1, "Mã NV"), (2, "Họ tên")):
        cell = ws.cell(row=1, column=col, value=label)
        cell.fill = header_fill
        cell.font = header_font

    # Field columns (start at column 3)
    for idx, field in enumerate(fields_config, start=3):
        label = field.get("label", field.get("key", f"field_{idx}"))
        unit = field.get("unit", "")

        cell = ws.cell(row=1, column=idx, value=label)
        cell.fill = header_fill
        cell.font = header_font

        if unit:
            ws.cell(row=2, column=idx, value=f"({unit})")

        # Data validation / number format
        field_type = field.get("type")
        col_letter = get_column_letter(idx)
        DATA_START_ROW = 3
        if field_type in {"select", "multi_select"}:
            options = field.get("options", [])
            if options:
                options_str = ",".join(str(o) for o in options)
                dv = DataValidation(
                    type="list", formula1=f'"{options_str}"', allow_blank=True
                )
                ws.add_data_validation(dv)
                dv.add(f"{col_letter}{DATA_START_ROW}:{col_letter}5000")
        elif field_type == "number":
            for row in range(DATA_START_ROW, 5000):
                ws[f"{col_letter}{row}"].number_format = "0.00"

    # Employee data rows (start at row 3)
    for row_offset, emp in enumerate(employees, start=3):
        emp_code_cell = ws.cell(row=row_offset, column=1, value=emp.get("employee_code", ""))
        name_cell = ws.cell(row=row_offset, column=2, value=emp.get("full_name", ""))
        emp_code_cell.fill = locked_fill
        name_cell.fill = locked_fill
        emp_code_cell.protection = emp_code_cell.protection.copy(locked=True)
        name_cell.protection = name_cell.protection.copy(locked=True)

        data = emp.get("data") or {}
        for idx, field in enumerate(fields_config, start=3):
            key = field.get("key")
            value = data.get(key)
            cell = ws.cell(row=row_offset, column=idx, value=value)
            cell.protection = cell.protection.copy(locked=False)

    # Protect sheet so locked columns A-B become read-only while data cells
    # (explicitly unlocked above) remain editable.
    ws.protection = SheetProtection(sheet=True, formatCells=False)
    ws.protection.enable()

    # Column widths
    total_cols = len(fields_config) + 2
    for col_idx in range(1, total_cols + 1):
        col_letter = get_column_letter(col_idx)
        max_len = 15
        for row in range(1, 3):
            v = ws.cell(row=row, column=col_idx).value
            if v:
                max_len = max(max_len, len(str(v)))
        ws.column_dimensions[col_letter].width = min(max_len + 2, 50)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def parse_department_import(
    file_content: bytes,
    fields_config: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Parse an uploaded Excel file for department import.

    Returns:
        (headers, rows) where:
        - headers: list of column headers from row 1
        - rows: list of dicts, each mapping field_key → value

    The first column must be ``employee_code`` (or ``Mã nhân viên``).
    Remaining columns are matched to fields_config keys (case-insensitive,
    trimmed). Unknown columns are reported in headers but not included in rows.

    Raises ValueError if the file is invalid or missing employee_code column.
    """
    try:
        wb = load_workbook(io.BytesIO(file_content), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"Không thể đọc file Excel: {exc}") from exc

    ws = wb.active
    if ws is None:
        raise ValueError("File Excel không có sheet hợp lệ.")

    # Read headers from row 1
    headers: list[str] = []
    try:
        row_one = list(ws[1])
    except IndexError:
        row_one = []
    for cell in row_one:
        val = cell.value
        if val is None:
            break
        headers.append(str(val).strip())

    if not headers:
        raise ValueError("File Excel không có tiêu đề cột (row 1).")

    # Find employee_code column (accept various Vietnamese labels)
    emp_code_col_idx = None
    EMPLOYEE_CODE_ALIASES = {
        "employee_code", "mã nhân viên", "ma_nv", "mã_nv", "mã nv", "ma nv",
    }
    for idx, header in enumerate(headers):
        if header.lower() in EMPLOYEE_CODE_ALIASES:
            emp_code_col_idx = idx
            break

    if emp_code_col_idx is None:
        raise ValueError(
            "Không tìm thấy cột 'employee_code' hoặc 'Mã NV' ở dòng 1."
        )

    # Find full_name column (to skip during data import)
    FULL_NAME_ALIASES = {"full_name", "họ tên", "ho_ten", "họ và tên", "ho va ten"}
    full_name_col_idx: int | None = None
    for idx, header in enumerate(headers):
        if header.lower() in FULL_NAME_ALIASES:
            full_name_col_idx = idx
            break

    # Build mapping: header → field_key (from fields_config)
    # Case-insensitive, trimmed matching
    field_keys = {f.get("key", "").lower().strip(): f.get("key") for f in fields_config}
    # Also build label → key mapping for Vietnamese label matching
    label_to_key = {
        f.get("label", "").lower().strip(): f.get("key")
        for f in fields_config
        if f.get("label")
    }
    header_to_key: dict[int, str] = {}
    skip_col_indices = {emp_code_col_idx}
    if full_name_col_idx is not None:
        skip_col_indices.add(full_name_col_idx)

    for col_idx, header in enumerate(headers):
        if col_idx in skip_col_indices:
            continue
        header_lower = header.lower().strip()
        # Direct match to field key
        if header_lower in field_keys:
            header_to_key[col_idx] = field_keys[header_lower]
        # Match by Vietnamese label (primary import format)
        elif header_lower in label_to_key:
            header_to_key[col_idx] = label_to_key[header_lower]
        # Fallback: partial label match
        else:
            for field in fields_config:
                label = field.get("label", "").lower().strip()
                if label and header_lower == label:
                    header_to_key[col_idx] = field.get("key")
                    break

    # Parse data rows (starting from row 2)
    rows: list[dict[str, Any]] = []
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not any(row):
            continue  # Skip empty rows

        # Extract employee_code
        emp_code = row[emp_code_col_idx] if emp_code_col_idx < len(row) else None
        if emp_code is None:
            emp_code = ""
        emp_code = str(emp_code).strip()

        row_dict: dict[str, Any] = {"employee_code": emp_code, "_row": row_idx}

        # Extract field values. Empty cells are skipped entirely so they do
        # NOT overwrite existing DepartmentResult data. A special sentinel
        # ``#CLEAR#`` explicitly clears a value.
        for col_idx, field_key in header_to_key.items():
            if col_idx >= len(row):
                continue
            value = row[col_idx]
            if isinstance(value, str) and value.strip() == "#CLEAR#":
                row_dict[field_key] = None  # explicit clear → seed/randomize
                continue
            if is_blank_value(value):
                continue  # empty/null cell → skip (preserve existing on re-import)
            row_dict[field_key] = value

        rows.append(row_dict)

    wb.close()
    return headers, rows
