"""Diagnosis services — import, findings aggregation, etc."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import openpyxl
from django.db import transaction

from diagnosis.models import DiagnosisKeyword

# Text values that mean "healthy / normal" and should never be treated as a
# finding.  Keeping this centralized prevents "Khỏe mạnh" (healthy) from being
# fed to the keyword matcher.
_NORMAL_VALUES = {
    "bình thường",
    "binh thuong",
    "normal",
    "khỏe mạnh",
    "khoe manh",
    "khỏe",
    "khoe",
    "âm tính",
    "am tinh",
    "-",
    "",
}


# Phân loại bệnh mắc (Excel col F) → Phân loại sức khỏe Loại I→V (1→5)
CLASSIFICATION_MAP: dict[float, int] = {
    0.0: DiagnosisKeyword.CLASSIFICATION_GOOD,     # Bình thường → Loại I
    5.0: DiagnosisKeyword.CLASSIFICATION_MILD,     # Nhẹ → Loại II
    2.0: DiagnosisKeyword.CLASSIFICATION_DISEASE,  # Bệnh mắc → Loại III
    1.0: DiagnosisKeyword.CLASSIFICATION_UNFIT,    # Không đủ ĐKLĐ → Loại V
}


def _normalize_classification(raw: Any) -> int | None:
    """Map an Excel classification value (col F) to keyword classification."""
    if isinstance(raw, (int, float)):
        return CLASSIFICATION_MAP.get(float(raw))
    return None


def import_keywords_from_excel(
    file_data: bytes, mode: str = "append"
) -> dict[str, int]:
    """Import DiagnosisKeyword rows from a Benh-TuVan xlsx file.

    Args:
        file_data: Raw bytes of the Excel file.
        mode: ``"replace"`` to delete all existing records first, or
              ``"append"`` (default) to add without deleting.

    Returns:
        Dict with keys ``diseases_created`` (kept for API compatibility, now 0),
        ``keywords_created``.
    """
    wb = openpyxl.load_workbook(BytesIO(file_data))
    ws = wb.active

    if mode == "replace":
        DiagnosisKeyword.objects.all().delete()

    keywords_created = 0

    with transaction.atomic():
        for row in ws.iter_rows(min_row=11, values_only=True):
            disease_name = row[0]
            keyword_text = row[1]
            conclusion = row[4]
            group_raw = row[5]
            alt_keyword = row[7]

            if not disease_name or not str(disease_name).strip():
                continue

            disease_name = str(disease_name).strip()
            conclusion = str(conclusion).strip() if conclusion else ""
            classification = _normalize_classification(group_raw)

            keyword_text = str(keyword_text).strip() if keyword_text else ""
            if keyword_text:
                _, created = DiagnosisKeyword.objects.get_or_create(
                    keyword=keyword_text,
                    defaults={
                        "disease_name": disease_name,
                        "conclusion_template": conclusion,
                        "classification": classification,
                        "is_active": True,
                    },
                )
                if created:
                    keywords_created += 1

            if alt_keyword and str(alt_keyword).strip():
                alt = str(alt_keyword).strip()
                if alt != keyword_text:
                    _, created = DiagnosisKeyword.objects.get_or_create(
                        keyword=alt,
                        defaults={
                            "disease_name": disease_name,
                            "conclusion_template": conclusion,
                            "classification": classification,
                            "is_active": True,
                        },
                    )
                    if created:
                        keywords_created += 1

    return {
        "diseases_created": 0,
        "keywords_created": keywords_created,
    }


def aggregate_findings(examination, skip_known_keywords: bool = True) -> str:
    """Build a findings text string from all DepartmentResult data values.

    Iterates every department result, looks up field definitions from
    ``template_snapshot``, and joins them. For number fields with
    ``abnormal_definitions``, out-of-range values are replaced with the
    abnormal label (e.g. HR=52 → "Nhịp tim chậm") instead of raw "label: value".

    Skips:
    - Numeric values within normal_range
    - Text values "bình thường"/"-"/"normal"
    - (optionally) values containing a known DiagnosisKeyword

    ``skip_known_keywords=True`` (default) is used for the raw ``findings``
    display. ``skip_known_keywords=False`` keeps matched values so the
    ``diagnosis`` matcher can still detect them (e.g. "cắt toàn bộ tuyến giáp"
    → keyword "toàn bộ tuyến giáp").

    Example output:
        ``"Nhịp tim chậm, Huyết sắc tố: 14.5, Á sừng da đầu"``
    """
    parts: list[str] = []
    # Pre-load active keywords for substring matching (case-insensitive)
    known_keywords = list(
        DiagnosisKeyword.objects.filter(is_active=True).values_list(
            "keyword", flat=True
        )
    )
    for dept_result in examination.department_results.all():
        snapshot = dept_result.template_snapshot or []
        data = dept_result.data or {}
        for field in snapshot:
            key = field.get("key")
            value = data.get(key)
            if value is None or value == "":
                continue
            field_type = field.get("type", "text")
            label = field.get("label", key)

            if field_type == "number":
                nr = field.get("normal_range")
                if nr and (nr.get("min") is not None or nr.get("max") is not None):
                    abnormal_defs = {
                        ad["direction"]: ad["label"]
                        for ad in field.get("abnormal_definitions", [])
                    }
                    try:
                        val = float(value)
                    except (TypeError, ValueError):
                        parts.append(f"{label}: {value}")
                        continue
                    lo, hi = nr.get("min"), nr.get("max")
                    if lo is not None and val < lo and "low" in abnormal_defs:
                        parts.append(abnormal_defs["low"])
                        continue
                    if hi is not None and val > hi and "high" in abnormal_defs:
                        parts.append(abnormal_defs["high"])
                        continue
                    # Value within normal range — skip it
                    if (lo is None or val >= lo) and (hi is None or val <= hi):
                        continue
            # Skip text values that literally indicate "normal"/healthy
            value_str = str(value).strip().lower()
            if value_str in _NORMAL_VALUES:
                continue
            # Skip values that match a known diagnosis keyword
            if skip_known_keywords and any(
                kw.lower() in value_str for kw in known_keywords
            ):
                continue
            parts.append(f"{label}: {value}")
    return ", ".join(parts)


def match_diagnosis(findings_text: str, limit: int = 20) -> list[dict[str, Any]]:
    """Match findings against DiagnosisKeyword to get disease name + consultation.

    Args:
        findings_text: Output from ``aggregate_findings()``.
        limit: Maximum number of results.

    Returns:
        List of dicts: ``{"keyword", "disease_name",
        "conclusion_template", "classification"}``, sorted by keyword.
    """
    if not findings_text.strip():
        return []

    raw_parts = [p.strip() for p in findings_text.split(",") if p.strip()]

    # Strip the "label: " prefix so keywords match the VALUE, not the field
    # label.  Abnormal labels (e.g. "Nhịp tim chậm") have no colon and stay
    # intact.  This prevents a generic keyword like "Tật" from matching the
    # field name "Tiền sử bệnh, tật".
    parts = []
    for p in raw_parts:
        if ": " in p:
            parts.append(p.split(": ", 1)[1])
        else:
            parts.append(p)

    keywords_qs = DiagnosisKeyword.objects.filter(
        is_active=True,
    ).order_by("keyword")

    all_keywords = list(keywords_qs)

    matches: list[dict[str, Any]] = []
    seen_diseases: set[str] = set()

    for part in parts:
        part_lower = part.lower()
        # For each finding, keep only the longest (most specific) keyword that
        # is a substring of it. This prevents a generic short keyword like
        # "Tật" from beating the specific "tật khúc xạ".
        best_kw = None
        for kw in all_keywords:
            if len(kw.keyword.strip()) < 3:
                continue
            kw_lower = kw.keyword.lower()
            if kw_lower in part_lower:
                if best_kw is None or len(kw.keyword) > len(best_kw.keyword):
                    best_kw = kw

        if best_kw and best_kw.disease_name and best_kw.disease_name not in seen_diseases:
            seen_diseases.add(best_kw.disease_name)
            matches.append(
                {
                    "keyword": best_kw.keyword,
                    "disease_name": best_kw.disease_name,
                    "conclusion_template": best_kw.conclusion_template,
                    "classification": best_kw.classification,
                }
            )

        if len(matches) >= limit:
            break

    return matches
