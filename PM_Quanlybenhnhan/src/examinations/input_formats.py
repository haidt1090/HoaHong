"""Input formatters for ``DepartmentField.input_format``.

Formatters rewrite a raw entered or imported value before it is stored.
They are keyed by format code, never by field key, so any text field can
opt in (e.g. blood pressure as ``bp_slash``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

INPUT_FORMAT_NONE = ""
INPUT_FORMAT_BP_SLASH = "bp_slash"

INPUT_FORMAT_CHOICES = [
    (INPUT_FORMAT_NONE, "—"),
    (INPUT_FORMAT_BP_SLASH, "Huyết áp (11280 → 112/80)"),
]


def format_bp_slash(value: Any) -> Any:
    """Insert ``/`` before the last two digits of a 4–5 digit integer.

    ``11280`` → ``112/80``, ``1280`` → ``12/80``. Values that already
    contain ``/``, or that are not a 4–5 digit integer, are left as-is
    (whitespace around an existing slash is stripped).
    """
    if value is None or isinstance(value, bool):
        return value

    if isinstance(value, float):
        if not value.is_integer():
            return value
        text = str(int(value))
        source_was_numeric = True
    elif isinstance(value, int):
        text = str(value)
        source_was_numeric = True
    else:
        text = str(value).strip()
        source_was_numeric = False

    if not text:
        return value

    compact = text.replace(" ", "")
    if "/" in compact:
        parts = compact.split("/")
        if (
            len(parts) == 2
            and parts[0].isdigit()
            and parts[1].isdigit()
            and parts[0]
            and parts[1]
        ):
            return f"{parts[0]}/{parts[1]}"
        return text if not source_was_numeric else value

    if compact.isdigit() and len(compact) in (4, 5):
        return f"{compact[:-2]}/{compact[-2:]}"

    return text if not source_was_numeric else value


FORMATTERS: dict[str, Callable[[Any], Any]] = {
    INPUT_FORMAT_BP_SLASH: format_bp_slash,
}


def apply_input_format(value: Any, field_def: dict[str, Any] | None) -> Any:
    """Apply the formatter named by ``field_def['input_format']``, if any."""
    if not field_def:
        return value
    code = field_def.get("input_format") or ""
    formatter = FORMATTERS.get(code)
    if formatter is None:
        return value
    return formatter(value)


def apply_formats_to_data(
    data: dict[str, Any], fields: list[dict[str, Any]]
) -> dict[str, Any]:
    """Return *data* with each value formatted from its field definition."""
    by_key = {f.get("key"): f for f in fields if f.get("key")}
    return {k: apply_input_format(v, by_key.get(k)) for k, v in data.items()}
