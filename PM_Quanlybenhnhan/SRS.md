# Software Requirements Specification — Hệ Thống Quản Lý Khám Sức Khỏe

## Phòng Khám Đa Khoa Y Cao Hoa Hồng

---

# 1. Introduction

## 1.1 Purpose
Build a clinic management system supporting periodic health checkups, occupational health exams, job placement exams, and labor exams (under/over 18). The system must work both online and offline with the same domain (`https://ycaohoahong.com/khamsk`), and include a CMS for non-technical staff to manage content.

## 1.2 Scope
- Data entry (manual, Excel import, QR scan)
- Print examination booklets (4 types)
- Reports (company summary with charts, clinical detail, occupational, cost)
- QR code generation for test tube labels and result lookup
- Online result delivery
- CMS for exam templates, diagnosis keywords, company/user management
- Offline-first PWA with background sync

## 1.3 Target Audience
- Clinic doctors, nurses, lab technicians
- Administrative staff
- Company HR personnel (view employee results)
- Patients (view personal results)

---

# 2. Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend | Django + Django REST Framework | Django 5.1+ |
| Database | PostgreSQL 16 + pgvector | 16 + 0.7+ |
| Async Tasks | Celery + Redis (or RabbitMQ) | — |
| Authentication | JWT (djangorestframework-simplejwt) | — |
| Embeddings | sentence-transformers (multilingual) | 3.0+ |
| PDF | WeasyPrint | — |
| Excel | openpyxl + django-import-export | — |
| Frontend | Vue.js (SPA) | latest LTS |
| Offline | PWA (Workbox + Dexie.js) | — |
| QR | qrcode (Python) + html5-qrcode (JS) | — |
| Charts | plotly or chart.js | — |
| Infrastructure | Docker Compose | — |

---

# 3. System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Client (Browser)                       │
│  ┌─────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │   React/Vue SPA  │  │  Service Worker │  │  IndexedDB   │  │
│  │  (Dynamic forms) │  │  (Cache + Sync) │  │ (Offline DB) │  │
│  └────────┬────────┘  └────────┬───────┘  └──────┬───────┘  │
└───────────┼────────────────────┼──────────────────┼──────────┘
            │ HTTP/REST          │ SW Events        │ IDB
            ▼                    ▼                  ▼
┌──────────────────────────────────────────────────────────────┐
│                     Django REST API                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Auth App │  │ Patient  │  │ Medical  │  │  Sync API    │  │
│  │          │  │ App      │  │ Exam App │  │  (pull/push) │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Diagnose │  │ Reports  │  │ QR/Print │  │  CMS Admin   │  │
│  │ (Vector) │  │ App      │  │ App      │  │  App         │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    Celery Workers                              │
│  ┌─────────────────┐  ┌────────────────┐                    │
│  │ Embedding Gen    │  │ Async Import   │                    │
│  │ (sentence-trans) │  │ (Excel parse)  │                    │
│  └─────────────────┘  └────────────────┘                    │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                 PostgreSQL 16 + pgvector                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │ Relational│  │ Vector   │  │ Full-text│                   │
│  │ Tables   │  │ Indexes  │  │ Search   │                   │
│  └──────────┘  └──────────┘  └──────────┘                   │
└──────────────────────────────────────────────────────────────┘
```

## 3.1 Data Flow

### Online Flow
```
User Action → SPA → REST API → Django View → DB → Response → SPA → Render
```

### Offline Flow
```
User Action → SPA → IndexedDB (local) → Queue changes → [Online] → REST API → DB
```

### Offline Read
```
SPA → Service Worker (cache-first) → Show cached data
  ↓ (if network)
REST API → Update cache → Show fresh data
```

---

## 3.2 Modular Django Apps

Each domain is a separate Django app with clear ownership and boundaries:

```
backend/
├── config/                    # Project root
│   ├── settings/
│   │   ├── base.py            # Shared settings (all environments)
│   │   ├── dev.py             # Development overrides
│   │   └── prod.py            # Production overrides
│   ├── urls.py                # Root URLconf (include per-app urls)
│   ├── wsgi.py / asgi.py
│   └── celery.py              # Celery app config
├── core/                      # Shared utilities (NOT a domain app)
│   ├── models.py              # BaseModel (id, created_at, updated_at), VersionedModel
│   ├── permissions.py         # Base DRF permission classes
│   ├── mixins.py              # Serializer mixins, viewset mixins
│   ├── utils.py               # Helpers (Excel parsing, encryption, embedding stub)
│   └── exceptions.py          # Custom API exceptions
├── accounts/                  # Auth & RBAC
│   ├── models.py              # User (roles), Company
│   ├── views.py               # Login, logout, profile, user CRUD
│   ├── serializers.py
│   └── permissions.py         # Role-based permission classes
├── patients/                  # Patient registry
│   ├── models.py              # Patient, ImportJob
│   ├── views.py               # Patient CRUD, search, Excel import
│   ├── serializers.py
│   ├── tasks.py               # Async Excel import (Celery)
│   └── signals.py             # post_create: generate embedding
├── examinations/              # Core medical data
│   ├── models.py              # Department, DepartmentTemplate, DepartmentField, ExamPackage, ExamPackageDepartment, Examination, DepartmentResult
│   ├── views.py               # Template CRUD, Exam CRUD, dynamic form render
│   ├── serializers.py
│   ├── validators.py          # Field validation against template schema
│   ├── widgets.py             # DepartmentTemplateAdmin field-builder widget (Sprint 4)
│   ├── permissions.py         # Department/Template/Package CRUD permissions
│   ├── admin.py               # Admin with builder widget, auto-created_by
│   ├── static/examinations/   # JS/CSS for the field builder
│   └── workflow.py            # Status transitions (draft→completed→confirmed)
├── diagnosis/                 # Vector search & Benh-TuVan
│   ├── models.py              # DiseaseCode, DiagnosisKeyword (+ VectorField)
│   ├── views.py               # Suggest diagnosis, similar cases, keyword CRUD
│   ├── serializers.py
│   ├── embeddings.py          # Embedding generation (Celery tasks)
│   └── management/commands/
│       └── reembed.py         # Management command to re-embed all keywords
├── reports/                   # PDF/Excel reports
│   ├── models.py              # Report
│   ├── views.py               # Generate, list, download
│   ├── tasks.py               # Async PDF generation (Celery)
│   └── templates/reports/     # WeasyPrint HTML templates
│       ├── company_summary.html
│       ├── clinical_detail.html
│       ├── occupational.html
│       ├── cost.html
│       └── booklet_*.html     # 4 booklet types
├── qrcodes/                   # QR generation & scanning
│   ├── models.py              # QRCode
│   ├── views.py               # Generate, batch, scan/decode
│   └── serializers.py
├── sync/                      # Offline sync protocol
│   ├── models.py              # SyncLog
│   ├── views.py               # Pull, push, status
│   └── serializers.py
├── cms/                       # Admin dashboard & CMS
│   ├── views.py               # Dashboard stats, template editor views
│   ├── serializers.py
│   └── templates/cms/         # (if server-rendered admin)
├── frontend/                  # SPA build output (collected by WhiteNoise)
└── manage.py
```

### App Responsibilities & URL Prefixes

| App | URL Prefix | Owns Models | Depends On |
|-----|-----------|-------------|------------|
| `accounts` | `/api/auth/` | User, Company | — |
| `patients` | `/api/patients/` | Patient, ImportJob | `accounts` (Company, User) |
| `examinations` | `/api/examinations/`, `/api/templates/`, `/api/packages/` | Department, DepartmentTemplate, DepartmentField, ExamPackage, ExamPackageDepartment, Examination, DepartmentResult | `patients` (Patient), `accounts` (User, CompanyExamPackage) |
| `diagnosis` | `/api/diagnosis/` | DiseaseCode, DiagnosisKeyword | `examinations` (Examination — for similar-case search) |
| `reports` | `/api/reports/` | Report | `examinations`, `patients` (Patient), `accounts` (Company) |
| `qrcodes` | `/api/qr/` | QRCode | `patients` (Patient), `examinations` |
| `sync` | `/api/sync/` | SyncLog | All other apps (reads all syncable models) |
| `cms` | `/api/admin/` | — (views only) | All other apps |

### Communication between Apps

**Rule: Prefer loose coupling. No circular imports.**

| Pattern | Use When | Example | Do Not Use When |
|---------|----------|---------|-----------------|
| **Direct FK / import** | Strong entity ownership, always needed | `Examination.patient = FK(Patient)` — `examinations` imports `patients.models.Patient` | Both apps need FK to each other (circular) |
| **Signals** | Side effects: "when X happens, also do Y" | `examinations.signals`: post_save Examination → trigger embedding generation in `diagnosis` | Core business logic; must know the caller |
| **Service layer** | Complex workflows spanning apps | `core.services.diagnosis_suggest(findings_text)` — called by `examinations` views | Simple queries (use ORM directly) |
| **Settings config** | Loose connection via config | `settings.CONCLUSION_GENERATOR = 'diagnosis.services.suggest_diagnosis'` — `examinations` reads via `import_module(SETTING)` | Hot-path queries (too slow) |
| **REST API call** | Cross-app in microservice split (future) | `examinations` calls `POST /api/diagnosis/suggest/` | Same-process apps (use services or signals) |

### Example: Writing a Conclusion after Exam Entry

```
1. Nurse fills clinical department result → PUT /api/examinations/{id}/departments/{dept_id}/
2. examinations/views.py saves the DepartmentResult
3. Signal: post_save(DepartmentResult) → triggers diagnosis.tasks.generate_exam_embedding.delay(exam_id)
4. Eventually, Doctor requests: POST /api/diagnosis/suggest/
   → diagnosis/services.py embeds aggregated findings text → pgvector search → returns top matches
5. Doctor selects diagnosis → writes conclusion → PATCH /api/examinations/{id}/
```

### Shared Core (`core/`)

The `core/` app has zero models and serves as a utility library:

```python
# core/models.py — Base mixins for all apps
class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class VersionedModel(BaseModel):
    version = models.IntegerField(default=1)
    class Meta:
        abstract = True

# core/exceptions.py
class SyncConflictError(APIException):
    status_code = 409
    default_detail = 'Version conflict — server has newer data'
    default_code = 'sync_conflict'

# core/utils.py
def embed_text(text: str) -> list[float]:
    """Return 384d embedding vector. Stub: replace with sentence-transformers pipeline."""
    pass

def encrypt_qr_id(raw_id: str) -> str:
    """AES-encrypt an ID for QR code content."""
    pass
```

---

# 4. Development Phases

## Phase 1 — Foundation (Sprints 1-3)

**Goal:** Project scaffold, auth, patient management, basic API
**Priority:** Critical

### Sprint 1: Project Scaffold
- [ ] Initialize Django project with config/ (dev/staging/production)
- [ ] Docker Compose: Django + PostgreSQL 16 + pgvector + Redis + Nginx
- [ ] django-environ for environment variables (.env)
- [ ] Python dependency management (poetry or pip-tools)
- [ ] Git init + .gitignore + pre-commit hooks (ruff, black)
- [ ] README with setup instructions
- [ ] Health check endpoint: `GET /api/health/`
- [ ] CORS configuration for PWA
- [ ] Logging configuration (console + file)
- [ ] Error handling middleware (standardized API errors)

### Sprint 2: Auth & User System
- [ ] Custom User model (AbstractUser)
  - Fields: email, phone, full_name, role, is_active, is_staff
- [ ] Roles: Admin, Doctor, Nurse, LabTech, CompanyAdmin
- [ ] Group-based permissions per role
- [ ] JWT authentication via djangorestframework-simplejwt
  - Access token (15 min) + Refresh token (7 days)
  - Token blacklist on logout
- [ ] Endpoints:
  - `POST /api/auth/login/`
  - `POST /api/auth/logout/`
  - `POST /api/auth/refresh/`
  - `GET /api/auth/me/`
  - `PUT /api/auth/me/` (update profile)
  - `POST /api/auth/change-password/`
- [ ] Admin user invite flow (create user → send credentials → first login forces password change)
- [ ] Rate limiting on login attempts

### Sprint 2a: Roles & Permissions

| Role | Who | Key Responsibilites |
|------|-----|---------------------|
| **Admin** (Quản trị viên) | System administrator | Full access: manage users, companies, templates, keywords, reports, settings, ALL data |
| **Doctor** (Bác sĩ) | Clinic doctor | View all patients; create/edit/confirm examinations; write conclusions; sign booklets; view all reports; view lab/xray/ultrasound data |
| **Nurse** (Điều dưỡng) | Nursing staff | View all patients; fill **clinical departments** (Lâm sàng, Mắt, Da liễu, TMH...); create draft examinations; print booklets; scan QR; cannot edit lab/imaging departments or conclusion |
| **LabTech** (Kỹ thuật viên) | Lab technician | View assigned patients; fill **lab/imaging departments** (Xét nghiệm, X-Quang, Siêu âm...); generate QR for test tubes; cannot edit clinical departments or conclusion |
| **CompanyAdmin** (Công ty) | Company HR | View own company's employee results; generate/download company reports; cannot edit any medical data |
| **Patient** (Bệnh nhân) | Public | View own result only via public portal (login: company_code + employee_code + DOB); download own PDF |

**Permission Matrix** (`Y` = Allowed, `N` = Forbidden):

| Resource | Admin | Doctor | Nurse | LabTech | CompanyAdmin | Patient |
|----------|-------|--------|-------|---------|-------------|---------|
| User CRUD | Y | N | N | N | N | N |
| Company CRUD | Y | view | N | N | N | N |
| Patient CRUD | Y | view_all | view_all | view_assigned | view_own_company | N |
| ExamTemplate CRUD | Y | view | view | view | N | N |
| Examination create | Y | Y | Y (draft) | N | N | N |
| Examination view | Y | all | all | assigned | own_company | own |
| Examination edit (department-level) | Y | all | clinical depts only | lab/imaging depts only | N | N |
| Examination confirm | Y | Y | N | N | N | N |
| Examination delete | Y | own draft | own draft | N | N | N |
| Conclusion write | Y | Y | N | N | N | N |
| Excel import | Y | Y | Y | N | N | N |
| QR generate | Y | Y | N | Y | N | N |
| QR scan (entry) | Y | Y | Y | Y | N | N |
| Reports generate | Y | Y | N | N | Y | N |
| Reports view | Y | all | all | view_own | own_company | N |
| PDF download | Y | Y | Y | N | Y | own |
| Sync (pull/push) | Y | Y | Y | Y | N | N |
| CMS (templates/keywords) | Y | N | N | N | N | N |
| System settings | Y | N | N | N | N | N |

**UI Enforcement Rules:**

- **Per-department access control**: Frontend shows all department tabs but disables/greys out departments the user cannot edit (e.g., LabTech sees clinical department tabs as read-only; Nurse sees lab/imaging department tabs as read-only)
- **Status workflow**: `draft` → `completed` → `confirmed`. Only `draft` exams can be deleted. `confirmed` exams are immutable except by Admin
- **Audit trail**: All edits logged with `user_id`, `action`, `timestamp`, and `changed_fields` (via django-simple-history)
- **Assignment**: Nurse and LabTech can optionally be assigned to specific companies/patients for filtered views

**Implementation tip**: Use Django permission groups + a custom mixin/permission class in DRF:

```python
# Example: per-field write control on ExaminationViewSet
class ExaminationPermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.role in ['doctor', 'admin']

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'doctor':
            return True
        if request.user.role == 'nurse':
            return obj.status == 'draft' and obj.doctor == request.user
        if request.user.role == 'labtech':
            return obj in request.user.assigned_examinations.all()
        return request.user.role == 'admin'
```

### Sprint 3: Patient Management
- [ ] Patient model:
  - company (FK → Company), employee_code, full_name
  - dob, gender (M/F), cccd, cccd_issued_date, cccd_issued_place
  - address, phone, email
  - department, start_date (ngày vào), toxic_factors
  - is_active, notes
- [ ] Company model:
  - name, address, tax_code, contact_person, contact_phone, contact_email
  - is_active
- [ ] Patient CRUD endpoints:
  - `GET /api/patients/` (list + search + filter)
  - `POST /api/patients/` (create)
  - `GET /api/patients/{id}/` (detail)
  - `PUT /api/patients/{id}/` (update)
  - `DELETE /api/patients/{id}/` (soft delete)
- [ ] Company CRUD endpoints
- [ ] Patient search: by name, employee_code, cccd, company_code, phone
- [ ] Pagination (page-based or cursor-based)
- [ ] Patient history timeline (examination history)

---

## Phase 2 — Examination Core (Sprints 4-6a)

**Goal:** Department-driven templates, dynamic examination entry with per-department results, multi-department Excel import, and company package pricing.
**Priority:** Critical

> **Architecture update (v2):** The app now uses a department-driven model instead of 5 hard-coded JSONFields. Each `Department` has its own `DepartmentTemplate` (tabular form). Departments are grouped into `ExamPackage`. A `DepartmentResult` row is created per department in each examination. See sprint files `docs/06.` through `docs/10.` for detailed implementation.

- **Sprint 4:** `Department` (with `category` for clinical/para-clinical RBAC), `DepartmentTemplate` + `DepartmentField` (field definitions as an indexed table, each field has `default_value`; admin field-builder + auto-generated key from label), `ExamPackage`, `ExamPackageDepartment` models. Each department has its own field table; packages group departments. `CompanyExamPackage.exam_package` is now a real FK to `ExamPackage`. `DepartmentTemplate.fields_config` is a read-only serialization property over `DepartmentField` rows (same JSON shape used by render API + `template_snapshot`).
- **Sprint 5:** `Examination` + `DepartmentResult` models. Multi-department examination entry, one `DepartmentResult` per department. Department-level role locking (Nurse edits clinical, LabTech edits lab/imaging). Admin add form: `exam_type` rendered as dropdown with choices; selecting `exam_package` auto-fills `exam_type` via AJAX (`package-exam-type/` endpoint).
- **Sprint 6:** Multi-department Excel import. Sheet-based or column-group mapping from `BANG THKQ KHAM.xlsx` to department fields.
- **Sprint 6a:** `CompanyExamPackage` model. Company-specific pricing: per-field or flat package total.

---

## Phase 3 — Diagnosis Engine (Sprints 7-8)

**Goal:** Import Benh-TuVan keywords, pgvector setup, semantic diagnosis suggestion
**Priority:** High

### Sprint 7: Keyword & Disease Management
- [ ] DiseaseCode model:
  - code: CharField (unique, e.g., "BNN01")
  - disease_name: TextField
  - icd_code: CharField (max_length=10, blank=True)
  - description: TextField (blank=True)
  - group: CharField (occupational / periodic / general)
- [ ] DiagnosisKeyword model:
  - keyword: TextField (the symptom/finding pattern)
  - disease: FK → DiseaseCode
  - conclusion_template: TextField (the conclusion text to output)
  - exam_type: CharField (which exam type this applies to)
  - priority: IntegerField (higher = matched first)
  - is_active: BooleanField
  - embedding: VectorField(dimensions=384, null=True)
- [ ] Import `Benh-TuVan 001.xlsx` → DiseaseCode + DiagnosisKeyword
  - `POST /api/diagnosis/import-keywords/`
- [ ] Keyword CRUD via API
- [ ] Keyword search + filter API

### Sprint 8: Vector Search Engine
- [ ] Django migration: `CreateExtension("vector")`
- [ ] pgvector VectorField on:
  - DiagnosisKeyword.embedding (384d)
  - DiseaseCode.embedding (384d)
  - Examination.embedding (384d) — for similar case search
  - Patient.embedding (384d) — for patient search
- [ ] Embedding generation service:
  - Model: `paraphrase-multilingual-MiniLM-L12-v2` (384d, multilingual including Vietnamese)
  - Run in Celery task
  - Generate on create/update of keywords
- [ ] Re-embed management command: `python manage.py reembed --model keyword`
- [ ] Diagnosis suggestion API:
  ```
  POST /api/diagnosis/suggest/
  Input:  { "findings_text": "Đau đầu, chóng mặt, men gan tăng", "exam_type": "periodic" }
  Output: [
    {
      "disease_code": "BNN05",
      "disease_name": "Bệnh gan nhiễm độc",
      "icd_code": "K71",
      "conclusion": "Người lao động có biểu hiện bệnh gan nhiễm độc",
      "confidence": 0.87,
      "matched_keywords": ["men gan tăng", "đau đầu"]
    }
  ]
  ```
- [ ] Backend logic:
  1. Embed findings_text
  2. `DiagnosisKeyword.objects.alias(distance=CosineDistance('embedding', embedded_text)).filter(distance__lte=0.4).order_by('-priority', 'distance')`
  3. Return top 5 results
  4. Fallback: keyword substring matching if vectors unavailable
- [ ] Similar case search API:
  ```
  POST /api/diagnosis/similar-cases/
  Input:  { "examination_id": 123 }
  Output: [{ "examination_id", "patient_name", "disease", "score" }]
  ```
- [ ] Admin action: "Re-embed all keywords" + "Test diagnosis suggestion"

---

## Phase 4 — Reports & Printing (Sprints 9-10)

**Goal:** PDF reports, Excel export, print booklets, charts
**Priority:** High

### Sprint 9: Report Generation ✅ Done
- [x] Report model:
  - company: FK → Company (nullable)
  - report_type: ChoiceField (company_summary / clinical_detail / occupational / cost)
  - parameters: JSONField (date range, filters)
  - status: ChoiceField (pending / generating / completed / failed)
  - file: FileField (upload_to='reports/')
  - generated_at: DateTimeField
  - created_by: FK → User
- [ ] Report templates (HTML + CSS rendered to PDF via WeasyPrint)
- [x] Report types:
  - **Company Summary Report**: 
    - Company info header
    - Summary statistics (total employees examined, abnormal count by category)
    - Charts: disease distribution (pie chart), abnormal rates by test (bar chart)
    - Employee list with results → 📋 Not started
  - **Clinical Detail Report**: ✅ Done
    - Per patient: all exam data organized by section
    - Doctor notes + diagnosis
  - **Occupational Report**: 📋 Not started
    - Toxic factors per employee
    - Occupational disease findings
    - Recommendation
  - **Cost Report**: 📋 Not started
    - Per employee: cost breakdown by item
    - Total per company
    - Summary by department
- [x] Report generation API:
  - `POST /api/reports/generate/` (async via Celery)
  - `GET /api/reports/` (list generated reports)
  - `GET /api/reports/{id}/download/` (download PDF/Excel)
  - `DELETE /api/reports/{id}/`
- [ ] Chart generation (plotly → static PNG embedded in PDF)

### Sprint 10: Print Booklets
- [ ] Print template for 4 booklet types:
  1. **Khám sức khỏe định kỳ** (Periodic Health Check)
  2. **Khám sức khỏe nghề nghiệp** (Occupational Health)
  3. **Khám bố trí nghề nghiệp** (Job Placement)
  4. **Khám lao động trên/dưới 18 tuổi** (Labor Under/Over 18)
- [ ] Print layout: A4 formatted for Vietnamese medical booklets
- [ ] Frontend print component:
  - Fetches examination data + renders print template
  - Uses `window.print()` with `@media print` CSS
  - Hides UI elements, shows only printable content
- [ ] Batch print: Select multiple patients → print all
- [ ] `GET /api/print/{exam_id}/preview/` (returns print-ready HTML)
- [ ] Cover page: clinic logo, patient info, QR code, barcode

---

## Phase 5 — Offline PWA (Sprints 11-12)

**Goal:** Service Worker, IndexedDB sync, conflict resolution, offline-first experience
**Priority:** High

### Sprint 11: PWA Setup
- [ ] Service Worker via Workbox webpack plugin
- [ ] Caching strategies:
  - Static assets (JS, CSS, fonts): Cache-First
  - API GET requests: Network-First with cache fallback
  - API POST/PUT/DELETE: Network-Only (queued if offline)
  - Images: Cache-First
- [ ] manifest.json:
  - name, short_name, description, icons (192px, 512px)
  - start_url: `/khamsk/`
  - display: `standalone`
  - background_color, theme_color
- [ ] Install prompt handling (beforeinstallprompt event)
- [ ] Offline fallback page (cached on first load)
- [ ] Online/offline indicator UI (green dot / red dot)
- [ ] Register service worker + update flow

### Sprint 12: Offline Data Sync
- [ ] IndexedDB database via Dexie.js:
  - Schema mirrors Django models (patients, examinations, templates, keywords, companies)
  - Versioned schema migrations
- [ ] Sync protocol:
  - **Pull** (`GET /api/sync/pull?since=<ISO_timestamp>&client_id=<uuid>`):
    ```json
    {
      "updated": [
        {"model": "Examination", "id": 1, "data": {...}, "version": 5, "updated_at": "..."}
      ],
      "deleted": [ {"model": "Examination", "id": 2} ],
      "server_time": "2026-07-01T12:00:00Z"
    }
    ```
  - **Push** (`POST /api/sync/push`):
    ```json
    {
      "client_id": "uuid",
      "changes": [
        {"model": "Examination", "id": null, "data": {...}, "version": 0, "operation": "create"},
        {"model": "Examination", "id": 5, "data": {...}, "version": 3, "operation": "update"}
      ]
    }
    ```
- [ ] Server-side sync logic:
  - Accept changes, check version conflicts
  - Create/update records, return new IDs and versions
  - Conflict response: `409 Conflict` with server version
- [ ] Conflict resolution:
  - Per-field merge: keep latest modification per field
  - Last-write-wins fallback
  - Conflicts flagged in SyncLog for admin review
- [ ] SyncLog model:
  - client_id, model_name, record_id, operation, version, status (synced / conflict), timestamp
- [ ] Background sync:
  - Register `sync` event in Service Worker
  - Queue failed pushes
  - Retry with exponential backoff
- [ ] Sync status UI:
  - Last synced time
  - Pending changes count
  - Conflicts count (with review link)
  - Force sync button
- [ ] Initial data load on first visit:
  - Download all templates, keywords, patients relevant to clinic
  - Store in IndexedDB

---

## Phase 6 — QR Code & Online Results (Sprints 13-14)

**Goal:** QR generation/printing, scanning for data entry, patient result portal
**Priority:** Medium

### Sprint 13: QR Code System
- [ ] QRCode model:
  - patient: FK → Patient
  - examination: FK → Examination (nullable)
  - code: CharField (encrypted unique identifier)
  - type: ChoiceField (test_tube / examination_booklet / result_lookup)
  - generated_at: DateTimeField
  - printed: BooleanField
- [ ] QR generation API:
  ```
  GET /api/qr/generate/?patient_id=X&type=test_tube
  → Returns PNG image (direct download or base64)
  ```
- [ ] QR content format:
  - Test tube: `https://ycaohoahong.com/khamsk/qr/test/<encrypted_id>`
  - Result lookup: `https://ycaohoahong.com/khamsk/qr/result/<encrypted_id>`
  - Booklet: `https://ycaohoahong.com/khamsk/qr/booklet/<encrypted_id>`
- [ ] Encryption for QR codes (AES or signed JWT, not raw IDs)
- [ ] Batch QR generation: `POST /api/qr/batch/`
  - Input: list of patient_ids + exam_type
  - Output: ZIP file of QR images or a PDF with labels
- [ ] QR scanning (frontend via html5-qrcode):
  - Camera access → scan QR → auto-fill patient for examination entry
  - Scan test tube QR → show patient + pending lab tests
  - Scan result QR → redirect to result portal
- [ ] Print QR on labels (CSS for label layout with patient name, exam date, QR code)

### Sprint 14: Online Result Portal
- [ ] Public-facing result lookup (no auth required, secured by QR + password):
  ```
  GET /khamsk/result/?code=<encrypted_qr_code>
  ```
- [ ] Alternative login:
  ```
  POST /api/results/login/
  Input: { company_code, employee_code, password: dob (YYYY-MM-DD) }
  Output: { token, patient_info }
  ```
- [ ] Result display page:
  - Patient info (name, dob, gender, company)
  - Examination date, type
  - Clinical findings (organized by section)
  - Lab results (with normal range indicators — green/red)
  - X-Ray result
  - Ultrasound result
  - Doctor's conclusion and diagnosis
  - PDF download button
- [ ] Security:
  - Rate limiting (5 attempts per IP per minute)
  - Token expiry (30 min)
  - Encrypted QR codes (cannot guess other patient's URL)
  - No PII in QR code itself
- [ ] Company admin view:
  - `GET /api/results/company/` (list all employees with results)
  - Filter by date range, department, status
  - Download batch results as ZIP
- [ ] Frontend: Mobile-responsive for patient access on phones

---

## Phase 7 — CMS Admin Panel (Sprint 15)

**Goal:** Admin dashboard, template editor, keyword manager, company/user management
**Priority:** Medium

### Sprint 15: Admin Interface
- [ ] Custom admin dashboard (can use django-grappelli or django-jazzmin as base, or build SPA admin)
- [ ] Dashboard widgets:
  - Patient count (today, this week, total)
  - Examinations today
  - Pending imports
  - Sync conflicts
  - Recent activity log
- [ ] Template Editor:
  - Visual form builder: drag-and-drop fields
  - Field types: text, number, select, multi-select, boolean, date, textarea
  - Section organization
  - Import from Excel (auto-generate template from column headers)
  - Version history
- [ ] Keyword Manager:
  - CRUD for DiseaseCode + DiagnosisKeyword
  - Bulk import from `Benh-TuVan 001.xlsx`
  - Test diagnosis: input findings text → see suggested matches
  - Re-embed keywords button
- [ ] Company Management:
  - CRUD for companies
  - Employee list per company
  - Import employee list from Excel
  - Company admin accounts
- [ ] User Management:
  - User CRUD + invite
  - Role assignment
  - Activity log per user
  - Login history
- [ ] Report Management:
  - Schedule recurring reports
  - Generated report history
  - Report template editor
- [ ] System Settings:
  - Clinic name, address, phone, email, logo
  - Print header/footer text
  - Default exam types
  - QR code settings (size, format)
  - Email configuration (for result notifications)

---

# 5. Database Design — Key Models

## 5.1 Django Core Models

```python
class Company(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    tax_code = models.CharField(max_length=20, blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Patient(models.Model):
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='patients')
    employee_code = models.CharField(max_length=50, blank=True)
    full_name = models.CharField(max_length=255)
    dob = models.DateField()
    gender = models.CharField(max_length=1, choices=[('M', 'Nam'), ('F', 'Nữ')])
    cccd = models.CharField(max_length=20, blank=True)
    cccd_issued_date = models.DateField(null=True, blank=True)
    cccd_issued_place = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    department = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(null=True, blank=True)
    toxic_factors = models.TextField(blank=True, help_text="Yếu tố độc hại")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    embedding = VectorField(dimensions=384, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'employee_code'],
                condition=models.Q(company__isnull=False),
                name='unique_employee_per_company'
            )
        ]

class CompanyExamPackage(BaseModel):
    PRICING_MODES = [
        ('per_field', 'Theo từng chỉ số'),
        ('package_total', 'Theo giá trọn gói'),
    ]
    company = models.ForeignKey(Company, on_delete=CASCADE, related_name='exam_packages')
    exam_package = models.ForeignKey('examinations.ExamPackage', on_delete=PROTECT, related_name='company_packages')
    pricing_mode = models.CharField(max_length=20, choices=PRICING_MODES)
    total_employees = models.PositiveIntegerField(default=0, help_text='Số lượng nhân viên được khám')
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=SET_NULL, null=True)

    class Meta:
        unique_together = ['company', 'exam_package']
        ordering = ['-assigned_at']

    @property
    def total_cost(self):
        """Computed: total_employees x package price (flat or per-field)."""

# === examinations/models.py ===

class Department(BaseModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=20, choices=[('clinical', 'Lâm sàng'), ('para_clinical', 'Cận lâm sàng')], default='clinical')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

class DepartmentTemplate(BaseModel):
    department = models.ForeignKey(Department, on_delete=CASCADE, related_name='templates')
    name = models.CharField(max_length=255)
    version = models.IntegerField(default=1)  # Auto-incremented on update; existing packages keep old version
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=SET_NULL, null=True)  # Auto-set to logged-in user; read-only in admin

    @property
    def fields_config(self) -> list[dict]:
        # Read-only serialization of DepartmentField rows into the legacy JSON
        # array shape. Consumed by render API + DepartmentResult.template_snapshot.
        return [f.as_config() for f in self.fields.all().order_by('order')]

class DepartmentField(BaseModel):
    # Field definitions live in a table (not a JSON array) for indexing + search.
    FIELD_TYPES = [('text','Text'),('number','Number'),('select','Select'),
                   ('multi_select','Multi-select'),('boolean','Boolean'),
                   ('date','Date'),('textarea','Textarea')]
    template = models.ForeignKey(DepartmentTemplate, on_delete=CASCADE, related_name='fields')
    key = models.CharField(max_length=100)              # auto-slugified from label
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default='text')
    unit = models.CharField(max_length=50, blank=True)
    required = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    normal_range = models.JSONField(null=True, blank=True)   # {"min": .., "max": ..}
    default_value = models.JSONField(null=True, blank=True)  # pre-fills DepartmentResult.data[key]
    default_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    test_category = models.CharField(max_length=50, blank=True)  # blood/urine/xray/... (Sprint 10a)
    options = models.JSONField(default=list, blank=True)     # for select / multi_select

    class Meta:
        ordering = ['order']
        constraints = [models.UniqueConstraint(fields=['template','key'], name='unique_field_key_per_template')]
        indexes = [models.Index(fields=['key']), models.Index(fields=['template','order'])]

    def as_config(self) -> dict:
        ...  # returns {key, label, type, order, required, unit?, normal_range?,
             #          default_value?, default_price?, test_category?, options?}

class ExamPackage(BaseModel):
    EXAM_TYPES = [
        ('periodic', 'Khám định kỳ'),
        ('occupational', 'Khám nghề nghiệp'),
        ('job_placement', 'Khám bố trí nghề nghiệp'),
        ('labor_under18', 'Khám lao động dưới 18'),
        ('labor_over18', 'Khám lao động trên 18'),
    ]
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    exam_type = models.CharField(max_length=50, choices=EXAM_TYPES)
    departments = models.ManyToManyField(Department, through='ExamPackageDepartment')
    default_package_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    is_active = models.BooleanField(default=True)

class ExamPackageDepartment(BaseModel):
    exam_package = models.ForeignKey(ExamPackage, on_delete=CASCADE)
    department = models.ForeignKey(Department, on_delete=CASCADE)
    template = models.ForeignKey(DepartmentTemplate, on_delete=PROTECT)
    order = models.IntegerField(default=0)
    class Meta:
        ordering = ['order']

class Examination(BaseModel, VersionedModel):
    STATUS_CHOICES = [
        ('draft', 'Nháp'),
        ('completed', 'Hoàn thành'),
        ('confirmed', 'Xác nhận'),
    ]
    patient = models.ForeignKey(Patient, on_delete=CASCADE, related_name='examinations')
    company_exam_package = models.ForeignKey(CompanyExamPackage, on_delete=PROTECT, null=True)
    exam_type = models.CharField(max_length=50, choices=ExamPackage.EXAM_TYPES)
    exam_date = models.DateField()
    conclusion = models.TextField(blank=True)
    disease = models.ForeignKey(DiseaseCode, on_delete=SET_NULL, null=True, blank=True)
    doctor = models.ForeignKey(User, on_delete=SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    @property
    def is_fully_filled(self):
        """True when every DepartmentResult has data for every field in its template_snapshot."""
        for dr in self.department_results.all():
            for col in dr.template_snapshot or []:
                val = dr.data.get(col.get("key"))
                if val is None or val == "":
                    return False
        return self.department_results.exists()

    def recompute_status(self):
        """Auto: all dept fields → completed, else → draft. Confirmed stays immutable."""
        if self.status == 'confirmed':
            return
        self.status = 'completed' if self.is_fully_filled else 'draft'
    version = models.IntegerField(default=1)
    embedding = VectorField(dimensions=384, null=True, blank=True)

class DepartmentResult(BaseModel, VersionedModel):
    examination = models.ForeignKey(Examination, on_delete=CASCADE, related_name='department_results')
    department = models.ForeignKey(Department, on_delete=PROTECT)
    template_snapshot = models.JSONField()
    data = models.JSONField(default=dict)
    completed_by = models.ForeignKey(User, on_delete=SET_NULL, null=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.IntegerField(default=1)

class DiseaseCode(models.Model):
    code = models.CharField(max_length=20, unique=True)
    disease_name = models.TextField()
    icd_code = models.CharField(max_length=10, blank=True)
    description = models.TextField(blank=True)
    group = models.CharField(max_length=50, default='general')
    embedding = VectorField(dimensions=384, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class DiagnosisKeyword(models.Model):
    keyword = models.TextField()
    disease = models.ForeignKey(DiseaseCode, on_delete=CASCADE, related_name='keywords')
    conclusion_template = models.TextField(blank=True)
    exam_type = models.CharField(max_length=50, blank=True)
    priority = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    embedding = VectorField(dimensions=384, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class QRCode(models.Model):
    QR_TYPES = [
        ('test_tube', 'Ống xét nghiệm'),
        ('booklet', 'Sổ khám'),
        ('result', 'Tra kết quả'),
    ]
    patient = models.ForeignKey(Patient, on_delete=CASCADE, related_name='qrcodes')
    examination = models.ForeignKey(Examination, on_delete=SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=20, choices=QR_TYPES)
    printed = models.BooleanField(default=False)
    generated_at = models.DateTimeField(auto_now_add=True)

class Report(models.Model):
    REPORT_TYPES = [
        ('company_summary', 'Báo Cáo Tổng Hợp Công Ty'),
        ('clinical_detail', 'Báo Cáo Chi Tiết'),
        ('occupational', 'Báo Cáo Nghề Nghiệp'),
        ('cost', 'Báo Cáo Chi Phí'),
    ]
    company = models.ForeignKey(Company, on_delete=CASCADE, null=True, blank=True)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES)
    parameters = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default='pending')
    file = models.FileField(upload_to='reports/', null=True, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SyncLog(models.Model):
    client_id = models.UUIDField()
    model_name = models.CharField(max_length=100)
    record_id = models.IntegerField(null=True)
    operation = models.CharField(max_length=10)  # create/update/delete
    version = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='synced')  # synced/conflict
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

## 5.2 PostgreSQL Extensions

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for fuzzy text search fallback
```

## 5.3 pgvector Indexes

```sql
-- For HNSW index (better for high-dimension, production)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_keyword_embedding
    ON diagnosis_keyword USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- For IVFFlat index (faster build, good for <100K rows)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_examination_embedding
    ON examination USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

---

# 6. API Reference Summary

## 6.1 Authentication
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login/` | Login, returns JWT |
| POST | `/api/auth/logout/` | Logout, blacklist token |
| POST | `/api/auth/refresh/` | Refresh token |
| GET | `/api/auth/me/` | Current user profile |
| PUT | `/api/auth/me/` | Update profile |
| POST | `/api/auth/change-password/` | Change password |

## 6.2 Companies
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/companies/` | List companies |
| POST | `/api/companies/` | Create company |
| GET | `/api/companies/{id}/` | Company detail |
| PUT | `/api/companies/{id}/` | Update company |
| DELETE | `/api/companies/{id}/` | Delete company |

## 6.3 Patients
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/patients/` | List + search + filter |
| POST | `/api/patients/` | Create patient |
| GET | `/api/patients/{id}/` | Patient detail with exam history |
| PUT | `/api/patients/{id}/` | Update patient |
| DELETE | `/api/patients/{id}/` | Soft delete |
| POST | `/api/patients/import/` | Bulk import from Excel |

## 6.4 Examination Templates
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/templates/` | List templates |
| POST | `/api/templates/` | Create template (nested `fields[]` → DepartmentField rows) |
| GET | `/api/templates/{id}/` | Template detail (incl. serialized `fields_config`) |
| PUT | `/api/templates/{id}/` | Update template (increments version; replaces `fields[]`) |
| DELETE | `/api/templates/{id}/` | Deactivate template |
| GET | `/api/templates/{id}/render/` | Get form JSON schema (fields_config array — same shape as before) |

## 6.5 Examinations
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/examinations/` | List (filterable by patient, company, date, type) |
| POST | `/api/examinations/` | Create examination (draft) |
| GET | `/api/examinations/{id}/` | Detail with all data |
| PUT | `/api/examinations/{id}/` | Update (increments version) |
| PATCH | `/api/examinations/{id}/status/` | Change status |
| GET | `/api/examinations/{id}/fields/` | Merged template + data for form |

## 6.6 Diagnosis
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/diagnosis/suggest/` | Suggest diagnosis from findings text |
| POST | `/api/diagnosis/similar-cases/` | Find similar examinations |
| GET | `/api/diagnosis/keywords/` | List keywords |
| POST | `/api/diagnosis/keywords/` | Create keyword |
| POST | `/api/diagnosis/import-keywords/` | Import from Excel |
| POST | `/api/diagnosis/re-embed/` | Trigger re-embedding of all keywords |

## 6.7 Reports
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/reports/generate/` | Generate report (async) |
| GET | `/api/reports/` | List generated reports |
| GET | `/api/reports/{id}/download/` | Download report file |
| DELETE | `/api/reports/{id}/` | Delete report |

## 6.8 Print
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/print/{exam_id}/preview/` | Print preview HTML |

## 6.9 QR Code
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/qr/generate/` | Generate single QR (query: patient_id, type) |
| POST | `/api/qr/batch/` | Batch generate QR codes |
| GET | `/api/qr/scan/{code}/` | Decode QR, return patient/exam info |

## 6.10 Results (Public)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/results/login/` | Login with company_code + employee_code + dob |
| GET | `/api/results/{token}/` | View result data |
| GET | `/api/results/{token}/pdf/` | Download result as PDF |
| GET | `/api/results/company/` | Company admin: list all employee results |

## 6.11 Import
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/import/excel/` | Upload Excel file for import |
| GET | `/api/import/{id}/status/` | Check import status and errors |

## 6.12 Sync
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/sync/pull/` | Pull changes since timestamp |
| POST | `/api/sync/push/` | Push local changes to server |
| GET | `/api/sync/status/` | Get sync status (pending, conflicts) |

## 6.13 CMS / Admin
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/dashboard/` | Dashboard stats |
| GET/POST | `/api/admin/disease-codes/` | Disease code CRUD |
| GET/POST | `/api/admin/companies/` | Company management |
| GET/POST | `/api/admin/users/` | User management |

---

> **Frontend implementation spec**: See [docs/UI-UX-Design.md](./docs/UI-UX-Design.md) for complete component hierarchy, Pinia stores, composables, TypeScript interfaces, and build priority.

# 7. Frontend Page Structure

```
/khamsk/
├── login
├── dashboard                    → Stats, pending exams, recent activity
├── patients/
│   ├── list                     → Searchable table
│   ├── create                   → Patient form
│   └── {id}/
│       ├── detail               → Patient info + exam history
│       ├── edit                 → Edit patient
│       └── examinations/        → List patient's exams
├── examinations/
│   ├── list                     → Filterable exam table
│   ├── create?patient=X         → New exam (dynamic form)
│   ├── {id}/
│   │   ├── edit                 → Edit exam (dynamic form)
│   │   └── print                → Print booklet preview
│   └── import                   → Excel import page
├── diagnosis/
│   └── suggest                  → Test diagnosis suggestion tool
├── reports/
│   ├── list                     → Generated reports
│   ├── generate                 → Report generation form
│   └── {id}                     → Report detail / download
├── qr/
│   ├── generate                 → Single QR generation
│   └── batch                    → Batch QR generation
├── sync/
│   └── status                   → Sync status, pending, conflicts
├── results                      → Company view of employee results
├── admin/
│   ├── dashboard
│   ├── templates                → Form builder
│   ├── keywords                 → Keyword manager
│   ├── companies                → Company CRUD
│   ├── users                    → User management
│   └── settings                 → System settings
├── result                       → Public result lookup (no auth)
│   ├── login                    → Company code + emp code + password
│   └── {token}                  → View result
└── offline-fallback             → Shown when offline and resource unavailable
```

---

# 8. Development Guidelines

## 8.1 Code Quality
- All code in English (variables, functions, comments), except UI labels and business content (which must be in Vietnamese)
- Django: Black + Ruff for formatting/linting
- Frontend: ESLint + Prettier
- Type hints on all Python functions
- DRF Serializers with explicit validation

## 8.2 Git Workflow
- Branch: `main` (production) + `develop` (integration) + `feature/*` (per task)
- Commit format: `[Phase-Sprint] Description` e.g., `[1-2] Add JWT auth with refresh token`
- PR required for merge to develop and main

## 8.3 Testing
- Django: pytest + pytest-django
- API tests for all endpoints
- Model tests for key business logic
- Celery task tests (with eager mode)
- Frontend: Vitest/Jest for unit tests

## 8.4 Documentation
- README: setup instructions
- API docs via drf-spectacular (Swagger UI at `/api/docs/`)
- Inline comments for complex business logic only

---

# 9. Deployment

## 9.1 Development
```bash
docker-compose up -d           # Start all services
docker-compose run web python manage.py migrate
docker-compose run web python manage.py createsuperuser
docker-compose run web python manage.py reembed --all
```

## 9.2 Production
- Docker Compose or Kubernetes
- Nginx reverse proxy → Gunicorn (Django) + WhiteNoise (static files)
- PostgreSQL with pgvector on dedicated instance
- Redis for Celery + caching
- S3/MinIO for uploaded files (reports, imported Excel)
- HTTPS via Let's Encrypt
- CI/CD via GitHub Actions

## 9.3 Environment Variables
```
DJANGO_SECRET_KEY=
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=ycaohoahong.com
DATABASE_URL=postgres://user:pass@host:5432/dbname
REDIS_URL=redis://host:6379/0
CORS_ALLOWED_ORIGINS=https://ycaohoahong.com
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
```

---

# 10. Glossary

| Vietnamese | English | Description |
|-----------|---------|-------------|
| Khám lâm sàng | Clinical exam | Physical examination findings |
| Xét nghiệm | Lab test | Blood/urine lab results |
| X-Quang | X-Ray | X-Ray imaging result |
| Siêu âm | Ultrasound | Ultrasound imaging result |
| Bệnh nghề nghiệp | Occupational disease | Disease caused by workplace factors |
| Yếu tố độc hại | Toxic factor | Harmful workplace exposure |
| Sổ khám | Examination booklet | Printed medical record booklet |
| Mã nhân viên | Employee code | Company employee identifier |
| Mã công ty | Company code | Company identifier |
| Kết luận | Conclusion | Doctor's final diagnosis/conclusion |
| Bố trí nghề nghiệp | Job placement | Fitness-for-work assessment |

---

*Document version 1.0 — Last updated: 2026-07-01*
