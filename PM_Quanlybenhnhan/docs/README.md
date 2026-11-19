# Development Docs — Per-Sprint SRS

Detailed, implementable specifications split from the master `../SRS.md`. Each file is a self-contained work package for a single sprint: goal, tasks, data models, endpoints, acceptance criteria, and definition of done.

> Naming convention: `NN. P<phase>-S<sprint>-<slug>.md`
> Prefix `F` = Frontend sprint (companion to backend)

## Index

| # | File | Sprint | Priority |
|---|------|--------|----------|
| 01 | [P1-S1 Project Scaffold](./01.%20P1-S1-project-scaffold.md) | 1 | 🔴 Critical |
| 02 | [P1-S2 Auth & User System](./02.%20P1-S2-auth-user-system.md) | 2 | 🔴 Critical |
| 03 | [P1-S2a Roles & Permissions](./03.%20P1-S2a-roles-permissions.md) | 2a | 🔴 Critical |
| 04 | [P1-S3 Patient Management](./04.%20P1-S3-patient-management.md) | 3 | 🔴 Critical |
| 05 | [P1-SF1 Frontend: App Shell & Patients](./05.%20P1-SF1-frontend.md) | F1 | 🔴 Critical |
| 06 | [P2-S4 Department & Template Engine](./06.%20P2-S4-dynamic-form-engine.md) | 4 | 🔴 Critical |
| 07 | [P2-S5 Examination Entry](./07.%20P2-S5-examination-entry.md) | 5 | 🔴 Critical |
| 08 | [P2-S6 Excel Import](./08.%20P2-S6-excel-import.md) | 6 | 🔴 Critical |
| 09 | [P2-S6a Company Package & Pricing](./09.%20P2-S6a-occupational-disease.md) | 6a | 🟡 High |
| 10 | [P2-SF1 Frontend: Exam UI & Packages](./10.%20P2-SF1-frontend.md) | F2 | 🔴 Critical |
| 11 | [P3-S7 Keyword & Disease Management](./11.%20P3-S7-keyword-disease-management.md) | 7 | 🟡 High |
| 12 | [P3-S8 Vector Search Engine](./12.%20P3-S8-vector-search-engine.md) | 8 | 🟡 High |
| 13 | [P4-S9 Report Generation](./13.%20P4-S9-report-generation.md) | 9 | 🟡 High |
| 14 | [P4-S10 Print Booklets](./14.%20P4-S10-print-booklets.md) | 10 | 🟡 High |
| 15 | [P4-S10a Test Screening Reports](./15.%20P4-S10a-test-screening.md) | 10a | 🟡 High |
| 16 | [P5-S11 PWA Setup](./16.%20P5-S11-pwa-setup.md) | 11 | 🟡 High |
| 17 | [P5-S12 Offline Data Sync](./17.%20P5-S12-offline-data-sync.md) | 12 | 🟡 High |
| 18 | [P6-S13 QR Code System](./18.%20P6-S13-qr-code-system.md) | 13 | 🟢 Medium |
| 19 | [P6-S14 Online Result Portal](./19.%20P6-S14-online-result-portal.md) | 14 | 🟢 Medium |
| 20 | [P7-S15 CMS Admin Panel](./20.%20P7-S15-cms-admin-panel.md) | 15 | 🟢 Medium |

## Phase Overview

| Phase | Focus | Sprints | Priority |
|-------|-------|---------|----------|
| 1 | Foundation: scaffold, auth, RBAC, patients, company packages + frontend | 1, 2, 2a, 3, F1 | 🔴 Critical |
| 2 | Examination Core: department templates, entry, import, company pricing + frontend | 4, 5, 6, 6a, F2 | 🔴 Critical |
| 3 | Diagnosis Engine: keywords, pgvector semantic search | 7, 8 | 🟡 High |
| 4 | Reports & Printing: PDF/Excel reports, booklets, test screening | 9, 10, 10a | 🟡 High |
| 5 | Offline PWA: Service Worker, IndexedDB sync | 11, 12 | 🟡 High |
| 6 | QR Code & Online Results: QR, patient portal | 13, 14 | 🟢 Medium |
| 7 | CMS Admin Panel: template editor, management | 15 | 🟢 Medium |

## How to Use

- Master reference and cross-cutting design live in [`../SRS.md`](../SRS.md).
- Pick a sprint file, work the task checklist top to bottom, satisfy the acceptance criteria, then the definition of done.
- Commit format: `[Phase-Sprint] Message` (e.g. `[1-2] Add JWT auth with refresh token`).

## Recent Additions

| Sprint | What | Reason |
|--------|------|--------|
| P1-SF1 | Phase 1 Frontend | App shell, auth pages, patient/company CRUD, package assignment UI |
| P2-S6a | Company Package & Pricing | Per-field and flat pricing per company |
| P2-SF1 | Phase 2 Frontend | Multi-tab departmental form, exam entry, company package assignment |
| P4-S10a | Test Screening | Filter by blood/urine/X-ray/ultrasound/lab/clinical abnormal results |

## Architecture v2 (Latest)

This project now uses a **department-driven architecture** (replacing 5 hard-coded JSONFields):

```
Department → DepartmentTemplate (tabular fields per department)
    ↓
ExamPackage = group of Departments (with template versions)
    ↓
CompanyExamPackage = ExamPackage + company-specific pricing (per-field or flat)
    ↓
Examination → spawns N DepartmentResult rows (one per department)
    ↓
Cost Report sums prices from CompanyExamPackage
```
