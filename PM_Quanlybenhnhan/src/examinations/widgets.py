"""
Custom admin widget for editing DepartmentTemplate.fields_config via a
dynamic row-based UI instead of raw JSON.

The widget renders a builder UI (add/remove rows, pick type, unit, normal
range, price, options...) plus a hidden ``<textarea>`` that holds the JSON
payload. The JS keeps the textarea in sync, so server-side validation in
``examinations.validators.validate_fields_config`` still applies unchanged.
"""

from __future__ import annotations

import json
from typing import Any

from django import forms


class FieldsConfigWidget(forms.Widget):
    """Row-based builder for a DepartmentTemplate ``fields_config`` array."""

    template_name = "examinations/widgets/fields_config.html"

    class Media:
        css = {"all": ("examinations/fields_config_builder.css",)}
        js = ("examinations/fields_config_builder.js",)

    def format_value(self, value: Any) -> str:
        """Return the value as a JSON string for the hidden textarea."""
        if value is None or value == "":
            return "[]"
        if isinstance(value, str):
            # Already a JSON string (e.g. re-render after validation error).
            return value
        return json.dumps(value, ensure_ascii=False)

    def value_from_datadict(self, data: Any, files: Any, name: str) -> Any:
        """Read the raw JSON string submitted by the hidden textarea."""
        return data.get(name)

    def get_context(self, name: str, value: Any, attrs: Any) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["value"] = self.format_value(value)
        return context


class GenderOverrideWidget(forms.Widget):
    """Compact editor for ``DepartmentField.gender_overrides``.

    Renders two rows (Nam / Nữ) each with min / max / step inputs, backed
    by a hidden textarea holding the JSON payload. The inline JS keeps the
    textarea in sync so server-side validation still sees plain JSON.
    """

    template_name = "examinations/widgets/gender_override.html"

    def format_value(self, value: Any) -> str:
        if value is None or value == "":
            return "{}"
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    def value_from_datadict(self, data: Any, files: Any, name: str) -> Any:
        return data.get(name)

    def get_context(self, name: str, value: Any, attrs: Any) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["value"] = self.format_value(value)
        return context
