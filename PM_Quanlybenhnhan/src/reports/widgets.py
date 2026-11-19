"""
Admin widgets for report template authoring (Sprint 9a).

``TemplateEditorWidget`` renders a textarea with syntax highlighting for HTML
and Django template tags, line numbers, a variable picker, and a preview
button.

Implementation note — the sprint doc specifies CodeMirror 6. CodeMirror 6 ships
as ESM modules that must be bundled or pulled from a CDN; this project has no
JS build step for Django admin assets and is deployed into environments that
may not have outbound internet access. The editor here is therefore a
dependency-free equivalent: a transparent textarea layered over a highlighted
``<pre>``, which gives the same authoring experience with no network fetch and
no bundler.
"""

from __future__ import annotations

import json
from typing import Any

from django import forms
from django.urls import NoReverseMatch, reverse

from reports.shortcodes import REPORT_VARIABLES


class TemplateEditorWidget(forms.Textarea):
    """Syntax-highlighting editor for Django-template HTML fragments."""

    template_name = "reports/widgets/template_editor.html"

    class Media:
        css = {"all": ("reports/template_editor.css",)}
        js = ("reports/template_editor.js",)

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        variable_groups: list[dict[str, Any]] | None = None,
        preview_kind: str = "",
    ) -> None:
        default_attrs = {
            "rows": 20,
            "spellcheck": "false",
            "autocomplete": "off",
            "style": "width:100%;box-sizing:border-box",
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)
        self.variable_groups = variable_groups or REPORT_VARIABLES
        # "report" | "department" — decides which preview endpoint to call.
        self.preview_kind = preview_kind

    def get_context(self, name: str, value: Any, attrs: Any) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["variable_groups_json"] = json.dumps(
            self.variable_groups, ensure_ascii=False
        )
        context["widget"]["preview_kind"] = self.preview_kind
        try:
            context["widget"]["guide_url"] = reverse("admin:reports_template_guide")
        except NoReverseMatch:
            context["widget"]["guide_url"] = ""
        return context


class PrettyJSONWidget(forms.Textarea):
    """Pretty-print JSONField values so config objects stay readable."""

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        default_attrs = {"rows": 6, "class": "vLargeTextField json-config"}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    def format_value(self, value: Any) -> str:
        if value in (None, ""):
            return "{}"
        if isinstance(value, str):
            try:
                return json.dumps(json.loads(value), indent=2, ensure_ascii=False)
            except (TypeError, ValueError):
                return value
        return json.dumps(value, indent=2, ensure_ascii=False)
