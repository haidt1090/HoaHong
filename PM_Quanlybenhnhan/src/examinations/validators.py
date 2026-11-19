"""
Validation for DepartmentTemplate ``fields_config`` schemas.

``fields_config`` is a flat array of column definitions. Each column is a
dict describing a single input in the department's tabular form.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

# Supported field input types for the dynamic form engine.
FIELD_TYPES = {
    "text",
    "number",
    "select",
    "multi_select",
    "boolean",
    "date",
    "textarea",
    "computed",
}


def _resolve_field_type(field: dict[str, Any]) -> str | None:
    """Return the effective field type, accepting ``type`` or ``field_type``."""
    return field.get("type") or field.get("field_type")


def validate_fields_config(value: Any) -> list[dict[str, Any]]:
    """
    Validate a ``fields_config`` payload (also used for ``fields[]``).

    Rules:
    - Must be a list.
    - Each item must be a dict with ``key``, ``label``, and either ``type``
      or ``field_type``.
    - Type must be one of :data:`FIELD_TYPES`.
    - ``key`` must be unique within the template and a non-empty string.
    - ``select`` / ``multi_select`` types must provide non-empty ``options``.
    - ``normal_range_min`` / ``normal_range_max`` must be numeric.
    - ``default_price`` (if present) must be a non-negative number.

    Returns the validated list unchanged.
    """
    if not isinstance(value, list):
        raise serializers.ValidationError("fields_config phải là một mảng (list).")

    seen_keys: set[str] = set()

    for index, field in enumerate(value):
        prefix = f"fields_config[{index}]"

        if not isinstance(field, dict):
            raise serializers.ValidationError(
                f"{prefix} phải là một đối tượng (object)."
            )

        # Normalize: DepartmentField uses ``field_type``; legacy payloads use ``type``.
        if "field_type" in field and "type" not in field:
            field["type"] = field["field_type"]

        for required_key in ("key", "label"):
            if required_key not in field:
                raise serializers.ValidationError(
                    f"{prefix} thiếu thuộc tính bắt buộc '{required_key}'."
                )

        key = field["key"]
        if not isinstance(key, str) or not key.strip():
            raise serializers.ValidationError(f"{prefix}.key phải là chuỗi không rỗng.")
        if key in seen_keys:
            raise serializers.ValidationError(f"{prefix}.key trùng lặp: '{key}'.")
        seen_keys.add(key)

        field_type = _resolve_field_type(field)
        if not field_type:
            raise serializers.ValidationError(
                f"{prefix} thiếu 'type' hoặc 'field_type'."
            )
        if field_type not in FIELD_TYPES:
            raise serializers.ValidationError(
                f"{prefix}.type '{field_type}' không hợp lệ. "
                f"Cho phép: {', '.join(sorted(FIELD_TYPES))}."
            )

        if field_type in {"select", "multi_select"}:
            options = field.get("options")
            if not isinstance(options, list) or not options:
                raise serializers.ValidationError(
                    f"{prefix}.options là bắt buộc và phải là mảng không rỗng "
                    f"cho type '{field_type}'."
                )

        for range_field in ("normal_range_min", "normal_range_max"):
            val = field.get(range_field)
            if val is not None:
                try:
                    float(val)
                except (TypeError, ValueError):
                    raise serializers.ValidationError(
                        f"{prefix}.{range_field} phải là số."
                    ) from None

        default_price = field.get("default_price")
        if default_price is not None:
            try:
                if default_price < 0:
                    raise serializers.ValidationError(
                        f"{prefix}.default_price không được là số âm."
                    )
            except TypeError:
                raise serializers.ValidationError(
                    f"{prefix}.default_price phải là số không âm."
                ) from None

    return value
