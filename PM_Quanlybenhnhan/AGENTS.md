# AGENTS.md

## Before You Edit
- Always commit current state before making changes.
- If the current branch is `main` or `master` or `staging`, create a new branch first.

## Before implement
- Review [SRS.md](./SRS.md) first before making changes.
- Review [UI-UX-Design.md](./docs/UI-UX-Design.md) for frontend component specs, API contracts, and TypeScript types.

## After finish sprint
- Ask them to complete everything, then mark the sprint as 'Done'.
- Update sprint status on [README.md](./README.md)

## Tech Stack
- Backend: Django 5.1+ / DRF / PostgreSQL 16 + pgvector / Celery + Redis
- Frontend: Vue SPA + PWA (Workbox + Dexie.js IndexedDB)
- Infra: Docker Compose (dev), Nginx + Gunicorn + WhiteNoise (prod)
- Key libs: djangorestframework-simplejwt, WeasyPrint, openpyxl, sentence-transformers (384d multilingual), qrcode, html5-qrcode

## Dev Commands (once scaffolded)
```
docker-compose up -d
docker-compose run web python manage.py migrate
docker-compose run web python manage.py createsuperuser
docker-compose run web python manage.py reembed --all
```

## Code Conventions
- Code/comments in English; UI labels and business content in Vietnamese
- Python: Black + Ruff, type hints on all functions
- Frontend: ESLint + Prettier
- Git: branches `main` / `develop` / `feature/*`; commits `[Phase-Sprint] Message`

## Architecture (non-obvious from filenames)
- **6 roles** with department-level RBAC: Admin, Doctor, Nurse, LabTech, CompanyAdmin, Patient. Permissions per department: Nurse edits clinical depts, LabTech edits lab/imaging depts.
- **Dynamic forms**: DepartmentTemplate has a JSONField `fields_config` (tabular columns per department); Departments are grouped into ExamPackage; Examination spawns DepartmentResult rows (one per department). Frontend renders multi-tab dynamic form.
- **Pricing**: CompanyExamPackage links a company to an ExamPackage with per-field or flat pricing mode. Cost reports compute totals per patient from template default_prices.
- **pgvector**: DiagnosisKeyword has 384d embeddings; suggest diagnosis via cosine distance on aggregated findings text from all DepartmentResult data. Model: `paraphrase-multilingual-MiniLM-L12-v2`
- **Offline-first**: Service Worker cache-first for static, network-first for API GET, queue POST/PUT/DELETE in IndexedDB when offline. Sync via `/api/sync/pull` and `/api/sync/push` with per-field versioned conflict resolution
- **QR codes**: Encrypted (not raw IDs) — types: test_tube, booklet, result_lookup. Patient result portal login: company_code + employee_code + DOB
- **Examination status workflow**: draft → completed → confirmed. Only draft can be deleted; confirmed is immutable except by Admin
- **4 booklet types**: định kỳ (periodic), nghề nghiệp (occupational), bố trí nghề nghiệp (job placement), lao động trên/dưới 18 tuổi

## Reference Data
- `documents/BANG THKQ KHAM.xlsx` — master exam data template (columns A-BX)
- `documents/Benh-TuVan 001.xlsx` — keyword → disease → conclusion mappings

## Report Template Engine (Sprint 9a) — Skill

The report module (`src/reports/`) generates PDF, HTML or Excel reports from
examination data using admin-authored Django templates. Understand this before
touching anything in `reports/`.

### Models

```
ReportTemplate                     ← composite: Excel letterhead + body
├── header_xlsx   (FileField)      ← uploaded .xlsx, static branding (merged as-is)
├── footer_xlsx   (FileField)      ← uploaded .xlsx, static branding (merged as-is)
├── body_type     (str)            ← chọn 1 trong 5 kiểu bên dưới
├── body_config   (JSON)           ← tham số cho body function
├── body_html     (txt, optional)  ← ghi đè template cho 4 kiểu coded
├── logo          (ImageField)
├── extra_css     (txt)            ← CSS bổ sung vào <style> của tài liệu HTML
├── page_size     (A4/A4L/A3L)
└── items ──→ ReportTemplateItem[]
                ├── department_template FK → DepartmentReportTemplate
                ├── department FK (nullable, auto-match)
                ├── exam_template FK (nullable, pin data-entry template)
                ├── order (int)
                └── page_break_before (bool)

DepartmentReportTemplate           ← body HTML cho 1 khoa
├── name, department (FK, nullable)
├── body_html (Django tpl)         ← {% for field in fields %}…{% endfor %}
└── config (JSON)

Report
├── company FK, report_type, output_format (pdf|html|xlsx)
├── template FK → ReportTemplate (nullable = fallback Excel cũ)
├── parameters JSON {exam_package_id, exam_date}
├── file (FileField → MEDIA_ROOT/reports/)
└── status (processing|done|failed) + error_message
```

### 5 body_type variants

| body_type | Cơ chế | Template sửa ở đâu? |
|---|---|---|
| `department_templates` | Duyệt `items[]`, render từng `DepartmentReportTemplate.body_html` | Admin → Department report templates |
| `clinical_detail_table` | Bảng ngang 1 dòng/NV, header merge 3 tầng | `ReportTemplate.body_html` (nếu trống → Python fallback) |
| `clinical_detail_blood_test` | Bảng máu dọc: NV = hàng, chỉ số = cột | `ReportTemplate.body_html` (nếu trống → Python fallback) |
| `summary_stats` | Thống kê: giới tính, phân loại SK, bệnh, khoa | `ReportTemplate.body_html` (nếu trống → Python fallback) |
| `cost_breakdown` | Bảng chi phí theo chỉ số hoặc trọn gói | `ReportTemplate.body_html` (nếu trống → Python fallback) |

### Key files & their roles

| File | Role |
|---|---|
| `reports/models.py` | All 5 models + Report, choice constants, guard properties |
| `reports/report_builder.py` | `build_report_dataset()` — nested PatientRecord→RenderedDepartment→RenderedField with `is_abnormal`; legacy `build_clinical_detail_report()` → flat ReportData |
| `reports/body_builder.py` | `BodyBuilder.render()`: template-or-fallback dispatch + `_ctx_*` context builders cho 4 coded types |
| `reports/render.py` | `render_report()` — body → HTML (letterhead is Excel-only); sandboxed `RestrictedEngine` |
| `reports/xlsx_letterhead.py` | Merge uploaded `header_xlsx` / `footer_xlsx` into report workbooks (cells, styles, merges, images) |
| `reports/preview.py` | `build_sample_dataset()` — dữ liệu giả để preview; `build_preview_dataset()` — dữ liệu thật với limit |
| `reports/shortcodes.py` | `REPORT_VARIABLES` — danh sách variable cho admin picker (body HTML) |
| `reports/widgets.py` | `TemplateEditorWidget` — highlight HTML+Django tag, variable picker, preview |
| `reports/static/reports/template_editor.js` | Editor frontend: highlight, line numbers, insert token, preview |
| `reports/tasks.py` | Celery `generate_report_task()` — Excel (+ letterhead merge) hoặc HTML body |
| `reports/management/commands/seed_report_templates.py` | Tạo 9 department + 5 composite template mặc định (idempotent) |

### Template context variables

**Report-level** (dùng trong `body_html`; Excel letterhead is static uploaded files):
`{{ clinic_name }}`, `{{ clinic_address }}`, `{{ clinic_phone }}`, `{{ logo_url }}`,
`{{ company.name }}`, `{{ company.code }}`, `{{ exam_date }}`, `{{ report_date }}`,
`{{ total_employees }}`, `{{ patients }}`, `{{ departments }}`, `{{ config }}`

**Department-level** (trong `DepartmentReportTemplate.body_html`):
`{{ department.name }}`, `{{ department.code }}`, `{{ patient.ho_ten }}`,
`{{ patient.ma_nv }}`, `{% for field in fields %}`, `{{ field.label }}`,
`{{ field.value }}`, `{{ field.unit }}`, `{{ field.normal_range }}`,
`{{ field.is_abnormal }}`, `{{ field.abnormal_direction }}`

**Type-specific** (trong `ReportTemplate.body_html`, do context builder cung cấp):
- `clinical_detail_table`: `d_header.r1/r2/r3/r4`, `d_rows[].cells[].text/abnormal`
- `clinical_detail_blood_test`: `d_columns[].label/unit/normal_range`, `d_rows[].stt/ma_nv/ho_ten/cells`
- `summary_stats`: `s_total`, `s_male/female`, `s_classifications[].label/count/pct`, `s_diseases`, `s_departments`
- `cost_breakdown`: `c_mode`, `c_lines[].dept/field/unit_price/count/line_total`, `c_grand_total`

### Guards (silent-failure prevention)

- **Items + non-department_templates**: admin formset clean() + API validate() → HTTP 400
- **body_html + department_templates**: API validate() → HTTP 400; admin body_type_help shows red warning
- **Render-time**: `logger.warning` khi template có orphaned items trong body_type không render chúng

### Common tasks

**Thêm body_type mới:**
1. Viết context builder `_ctx_xxx(dataset, config, context) → dict` trong `body_builder.py`
2. Viết Python fallback `def xxx(dataset, config, context) → str` trong `body_builder.py`
3. Register cả 2 vào `BodyBuilder.REGISTRY` và `BodyBuilder._CONTEXT_BUILDERS`
4. Thêm choice vào `ReportTemplate.BODY_TYPE_CHOICES` (`models.py`)
5. Thêm template body_html mặc định vào `seed_report_templates.py`

**Sửa template mặc định:**
1. Sửa `BODY_*` constant trong `seed_report_templates.py`
2. Chạy `python manage.py seed_report_templates` để update

**Debug render:**
```python
from reports.render import render_report
from reports.report_builder import build_report_dataset
from accounts.models import CompanyExamPackage
cep = CompanyExamPackage.objects.get(company__code="ABC")
ds = build_report_dataset(cep)
html = render_report(template, ds)
open("/tmp/out.html", "w").write(html)
```

**Deploy production:**
```bash
docker compose exec web python src/manage.py seed_report_templates
```

### Test suite
```bash
# Chỉ reports app
pytest src/reports/ -q

# File chính
pytest src/reports/test_dynamic_templates.py -q
```
