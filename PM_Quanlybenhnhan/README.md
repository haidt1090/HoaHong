# Quản lý bệnh nhân — Health Checkup Management System

## Prerequisites
- Docker and Docker Compose
- Python 3.12+ if running locally

## Quick start

1. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
2. Start the stack:
   ```bash
   docker-compose up -d --build
   ```
3. Run migrations:
   ```bash
   docker-compose run --rm web python src/manage.py migrate
   ```
4. Create a superuser:
   ```bash
   docker-compose run --rm web python src/manage.py createsuperuser
   ```
5. Open the API health check:
   ```bash
   curl http://localhost:8000/api/health/
   ```

## Services
- Web app: http://localhost:8000
- Nginx proxy: http://localhost:8080
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## Environment
All runtime configuration is loaded from `.env` using `django-environ`.

## Notes
- The database uses the `pgvector/pgvector:pg16` image so the `vector` extension is available.
- Static files are served by WhiteNoise in Django and proxied by Nginx in the compose stack.

## Sprint Progress

| Phase | Sprint | Description | Status |
|-------|--------|-------------|--------|
| **1 — Foundation** | P1-S1 | Project scaffold (Docker, Django, core app) | ✅ Done |
| | P1-S2 | Auth & User system (JWT, roles, invite) | ✅ Done |
| | P1-S2a | Roles & Permissions (6-role RBAC, department-level) | ✅ Done |
| | P1-S3 | Patient & Company management, CompanyExamPackage stub | ✅ Done |
| | P1-SF1 | Frontend: App shell & patient/company UI | ✅ Done |
| **2 — Examination Core** | P2-S4 | Department & Template engine (DepartmentTemplate, ExamPackage) | ✅ Done |
| | P2-S5 | Examination entry (Examination, DepartmentResult, status workflow) | ✅ Done |
| | P2-S6 | Excel import (per-department, async, template download) | ✅ Done |
| | P2-S6a | Company package assignment & pricing (per-field / package total) | ✅ Done |
| | P2-S4a | Allow duplicate departments in exam package (different templates) | ✅ Done |
| | P2-S4b | Department hierarchy (parent-child) | ✅ Done |
| | P2-SF1 | Frontend: Multi-tab exam form & package UI | ✅ Done |
| | P2-SF2 | Keyboard shortcuts & data entry UX (Ctrl+S, Ctrl+Q, ...) | 📋 Not started |
| **3 — Diagnosis** | P3-S7 | Keyword & Disease management | ✅ Done |
| | P3-S8 | Vector search engine (pgvector, embedding, diagnosis suggest) | 📋 Not started |
| **4 — Reports** | P4-S9 | Report generation — Excel export (superseded by S9a) | ✅ Done |
| | P4-S9a | Dynamic Report Template Engine (HTML/PDF, shortcode, department templates) | ✅ Done |
| | P4-S10 | Print booklets (4 types, batch print, A4 layout) | 📋 Not started |
| | P4-S10a | Test screening reports (abnormal filter, Excel export) | 📋 Not started |
| **5 — Offline PWA** | P5-S11 | PWA setup (Service Worker, Workbox, manifest) | 📋 Not started |
| | P5-S12 | Offline data sync (IndexedDB, pull/push, conflict resolution) | 📋 Not started |
| **6 — QR & Portal** | P6-S13 | QR code system (encrypted, batch, scanning) | 📋 Not started |
| | P6-S14 | Online result portal (public patient access) | 📋 Not started |
| **7 — Admin** | P7-S15 | CMS Admin panel (dashboard, visual editor, settings) | 📋 Not started |
| **8 — Integration** | P8-S16 | National Health Portal data sync (CSDLKSK liên thông) | ✅ Done |

## Deploy Notes

Sau khi deploy + migrate, chạy các lệnh seed (idempotent — an toàn chạy lại nhiều lần):

```bash
# Sprint 9a: Seed report templates mặc định
docker compose exec web python src/manage.py seed_report_templates

# Phase 3: Re-embed diagnosis keywords (sau mỗi lần đổi model embedding)
# docker compose exec web python src/manage.py reembed --all
```
