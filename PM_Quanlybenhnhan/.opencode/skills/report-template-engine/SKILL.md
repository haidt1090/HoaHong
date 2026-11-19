---
name: report-template-engine
description: Work with the dynamic report template engine (Sprint 9a). Use when creating, editing, or debugging report templates, department templates, body types, template context variables, or the render pipeline (HTML/PDF/Excel).
license: proprietary
compatibility: opencode
metadata:
  app: reports
  sprint: P4-S9a
  phase: 4
---

## What I Do

I provide the architecture and conventions for the dynamic report template
engine in `src/reports/`. This covers:

- 5 body types (`department_templates`, `clinical_detail_table`,
  `clinical_detail_blood_test`, `summary_stats`, `cost_breakdown`)
- How each body type works (Python fallback vs. admin-authored template)
- Model relationships and guard properties
- Template context variables at every level
- The render pipeline (dataset → context → header/body/footer → HTML → PDF)
- Admin editor widgets and preview endpoints
- How to seed default templates
- How to test changes

## When to Use Me

Load this skill when you are asked to:

- Create a new body type
- Modify a body function or its default template
- Change the template context variables
- Debug why a template does not render
- Work with `DepartmentReportTemplate` or `ReportTemplateItem`
- Understand the render flow (`report_builder` → `body_builder` → `render`)
- Update seed templates
- Add or modify the admin template editor

## Architecture

```
ReportTemplate (composite)
├── header_xlsx     ← uploaded .xlsx letterhead (static; merged into Excel as-is)
├── footer_xlsx     ← uploaded .xlsx letterhead (static; merged into Excel as-is)
├── body_type       ← "department_templates" | "clinical_detail_table" | …
├── body_config     ← JSON params cho body function
├── body_html       ← optional: overrides the Python body builder (4 coded types only)
├── logo (ImageField), extra_css, page_size (A4/A4L/A3L)
└── items → ReportTemplateItem[]
      ├── department_template FK → DepartmentReportTemplate
      ├── department FK (nullable, auto-match)
      ├── exam_template FK (nullable, pin data-entry template — Sprint 4a duplicates)
      ├── order (int)
      └── page_break_before (bool)

DepartmentReportTemplate
├── name, department FK (nullable = global)
├── body_html (Django tpl)  ← {% for field in fields %}…
└── config (JSON)

Report
├── company FK, report_type, output_format (pdf|html|xlsx)
├── template FK → ReportTemplate (nullable = fallback Excel cũ)
├── parameters JSON {exam_package_id, exam_date}
├── file (FileField → MEDIA_ROOT/reports/)
└── status (processing|done|failed) + error_message
```

## 5 Body Types

| body_type                    | Cơ chế                                           | Template source                         |
| ---------------------------- | ------------------------------------------------- | --------------------------------------- |
| `department_templates`       | Duyệt `items[]`, render `DepartmentReportTemplate` per department | Admin → Department report templates     |
| `clinical_detail_table`      | Bảng ngang, 1 dòng/NV, header merge 3 tầng         | `ReportTemplate.body_html` (or Python)  |
| `clinical_detail_blood_test` | Bảng máu dọc, NV = hàng, chỉ số = cột              | `ReportTemplate.body_html` (or Python)  |
| `summary_stats`              | Thống kê: giới tính, phân loại SK, bệnh, khoa      | `ReportTemplate.body_html` (or Python)  |
| `cost_breakdown`             | Bảng chi phí theo chỉ số hoặc trọn gói              | `ReportTemplate.body_html` (or Python)  |

Only `department_templates` reads `ReportTemplateItem` rows.
The other 4 types use `ReportTemplate.body_html` as an **override** — when
blank, Python code in `body_builder.py` builds the HTML.

## Key Files

| File | Role |
|---|---|
| `src/reports/models.py` | 5 models + Report, choice constants, guard properties (`has_orphaned_items`, `wastes_body_html`) |
| `src/reports/report_builder.py` | `build_report_dataset()` → nested `PatientRecord→RenderedDepartment→RenderedField` with `is_abnormal`. Legacy `build_clinical_detail_report()` → flat `ReportData` (attached as `dataset.table`) |
| `src/reports/body_builder.py` | `BodyBuilder.render()`: dispatches body_type → template path (if `body_html` set) or Python fallback. `_CONTEXT_BUILDERS` map body_type to context-builder functions that pre-compute template-friendly data |
| `src/reports/render.py` | `render_report()`: body-only HTML document (no HTML letterhead). `render_to_pdf()` via WeasyPrint. `RestrictedEngine`: sandbox with `include/extends/ssi/load/debug` tags removed **without mutating global singletons** (uses `_RestrictedLibrary` read-only wrapper) |
| `src/reports/xlsx_letterhead.py` | Merge uploaded `header_xlsx` / `footer_xlsx` into Excel (cells, styles, merges, images) |
| `src/reports/preview.py` | `build_sample_dataset()` — fake data for preview. `build_preview_dataset()` — real data truncated to limit |
| `src/reports/shortcodes.py` | `REPORT_VARIABLES` — documented variable surface for the admin picker |
| `src/reports/widgets.py` | `TemplateEditorWidget` — syntax highlighting, line numbers, variable picker, preview button (dependency-free: transparent textarea over highlighted `<pre>`) |
| `src/reports/static/reports/template_editor.js` | Editor frontend: highlight, insert token, preview via AJAX |
| `src/reports/tasks.py` | Celery `generate_report_task()`: template path (HTML→PDF) or legacy Excel |
| `src/reports/permissions.py` | `ReportTemplatePermission` (admin-only write, clinical-staff read), `ReportPermission` |
| `src/reports/serializers.py` | `ReportTemplateSerializer` with `validate()` guards, `GenerateReportSerializer` |
| `src/reports/views.py` | `ReportTemplateViewSet`, `DepartmentReportTemplateViewSet`, `ReportViewSet` with preview endpoints |
| `src/reports/admin.py` | Admin with `ReportTemplateItemInline` (with formset guard), `body_type_help` status line, custom `change_form_template` that lifts inline above layout |
| `src/reports/management/commands/seed_report_templates.py` | 9 department + 5 composite templates (idempotent) |

## Template Context Variables

### Report-level (body_html; Excel letterhead is separate)

Letterhead for Excel is static uploaded `.xlsx` (`header_xlsx` / `footer_xlsx`) —
no Django placeholders. HTML/PDF export renders **body only**.

```
{{ clinic_name }} {{ clinic_address }} {{ clinic_phone }}
{{ logo_url }} {{ company.name }} {{ company.code }}
{{ exam_date }} {{ report_date }} {{ total_employees }}
{{ patients }} {{ departments }} {{ config }}
```

### Department-level (DepartmentReportTemplate.body_html)

```
{{ department.name }} {{ department.code }}
{{ patient.ho_ten }} {{ patient.ma_nv }} {{ patient.ngay_sinh }}
{% for field in fields %}
  {{ field.label }} {{ field.value }} {{ field.display }}
  {{ field.unit }} {{ field.normal_range }}
  {{ field.is_abnormal }} {{ field.abnormal_direction }}
{% endfor %}
{{ abnormal_fields }} {{ has_abnormal }}
```

### Type-specific (ReportTemplate.body_html for coded types)

**clinical_detail_table:**
`d_header.r1/r2/r3/r4[].label/span/rowspan`, `d_rows[].cells[].text/abnormal`

**clinical_detail_blood_test:**
`d_columns[].label/unit/normal_range`, `d_rows[].stt/ma_nv/ho_ten/cells[]`

**summary_stats:**
`s_total`, `s_male/s_female`, `s_male_pct/s_female_pct`,
`s_classifications[].label/count/pct`, `s_diseases[].name/count/pct`,
`s_departments[].name/examined/abnormal`

**cost_breakdown:**
`c_mode`, `c_lines[].dept/field/unit_price/count/line_total`,
`c_grand_total`, `c_per_patient[].name/amount` (pre-formatted with dots)

## Guards (Silent-Failure Prevention)

| Guard | Mechanism |
|---|---|
| Items on non-department_templates body_type | Admin formset `clean()` + API `validate()` → HTTP 400 |
| body_html on department_templates | API `validate()` → HTTP 400; admin `body_type_help` shows red warning |
| body_type switched away while items exist | API `validate()` + admin formset → HTTP 400 |
| Render-time orphaned items | `logger.warning` in `render_report()` |
| Sandbox breaking global Django | `RestrictedEngine` + `_RestrictedLibrary` wrapper; test asserts tags remain in `defaulttags.register` |
| API-created items losing exam_template pin | `_sync_items()` forwards `exam_template`; test asserts |

## Common Tasks

### Add a new body_type

1. Write context builder `_ctx_xxx(dataset, config, context) → dict` in `body_builder.py`
2. Write Python fallback `def xxx(dataset, config, context) → str` in `body_builder.py`
3. Register both in `BodyBuilder.REGISTRY` and `BodyBuilder._CONTEXT_BUILDERS`
4. Add choice to `ReportTemplate.BODY_TYPE_CHOICES` in `models.py`
5. Add default `body_html` template to `seed_report_templates.py`

### Modify a default template

1. Edit the `BODY_*` constant in `seed_report_templates.py`
2. Run `python manage.py seed_report_templates` (idempotent — updates by name)

### Debug a render

```python
from reports.render import render_report
from reports.report_builder import build_report_dataset
from accounts.models import CompanyExamPackage

cep = CompanyExamPackage.objects.get(company__code="ABC")
ds = build_report_dataset(cep)
html = render_report(template, ds)
open("/tmp/out.html", "w", encoding="utf-8").write(html)
```

### Deploy to production

```bash
docker compose exec web python src/manage.py seed_report_templates
```

## Testing

```bash
# Reports only
pytest src/reports/ -q

# All tests
pytest src/ -q
```

94 tests in `src/reports/test_dynamic_templates.py` cover: model constraints,
dataset construction, abnormal detection, render engine, sandbox isolation,
body builder dispatch + template path, context builders, API validation,
admin formset guards, admin layout ordering, seed idempotence, and
generate_report_task template/fallback paths.

## Important Design Decisions

- **Not CodeMirror 6**: CodeMirror 6 is ESM and needs a bundler/CDN.
  The custom `TemplateEditorWidget` (transparent textarea over highlighted
  `<pre>`) achieves the same editing experience with zero dependencies.
- **No dict lookup by variable key**: Django templates cannot do `{{ dict[var] }}`.
  Context builders pre-structure data as flat lists of cell dicts so templates
  iterate with plain `{% for %}` loops.
- **`pydyf` pin**: WeasyPrint 62.x only works with pydyf 0.10 API.
  `pydyf>=0.10,<0.11` is required.
- **Route prefix**: Canonical routes are `/api/report-templates/` and
  `/api/department-report-templates/`. The spec's `/api/templates/report/`
  exists as alias but requires `reports.urls` to be included **before**
  `examinations.urls` in `config/urls.py` (otherwise `/api/templates/{pk}/`
  swallows the path segments).
