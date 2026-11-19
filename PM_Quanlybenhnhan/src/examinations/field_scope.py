"""Gender applicability for ``DepartmentField.applies_to``.

A field can be limited to male or female patients (e.g. abdominal
ultrasound for women). Applicability is stored on the field, never inferred
from the field key.
"""

from __future__ import annotations

from typing import Any

APPLIES_TO_ALL = "all"
APPLIES_TO_MALE = "M"
APPLIES_TO_FEMALE = "F"

APPLIES_TO_CHOICES = [
    (APPLIES_TO_ALL, "Tất cả"),
    (APPLIES_TO_MALE, "Nam"),
    (APPLIES_TO_FEMALE, "Nữ"),
]


def applies_to_code(field_def: dict[str, Any] | None) -> str:
    if not field_def:
        return APPLIES_TO_ALL
    code = field_def.get("applies_to") or APPLIES_TO_ALL
    if code in ("", None):
        return APPLIES_TO_ALL
    return str(code)


def field_applies_to_gender(
    field_def: dict[str, Any] | None, gender: str | None
) -> bool:
    """True if the field should be shown / count toward completeness.

    Unknown gender still applies (the form stays visible). A known mismatch
    (male + female-only) does not.
    """
    code = applies_to_code(field_def)
    if code == APPLIES_TO_ALL:
        return True
    if not gender:
        return True
    return gender == code


def should_seed_field(field_def: dict[str, Any] | None, gender: str | None) -> bool:
    """True if default/random/formula seed may run for this patient.

    Restricted fields are not seeded when gender is missing or does not match,
    so males do not receive female-only defaults (and vice versa).
    """
    code = applies_to_code(field_def)
    if code == APPLIES_TO_ALL:
        return True
    if not gender:
        return False
    return gender == code
