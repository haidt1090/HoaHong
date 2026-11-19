# Frontend — Hệ Thống Quản Lý Khám Sức Khỏe

Vue 3 + Vite SPA (companion to the Django backend). Implements Phase 1 Sprint F1:
app shell, auth, patient/company CRUD, and company package assignment.

## Tech Stack

- **Vue 3** (Composition API, `<script setup>`)
- **Vite** build tool (base path `/khamsk/`)
- **Vue Router 4** — lazy-loaded routes + auth/role guards
- **Pinia** — auth, patient, company stores
- **Axios** — API client with JWT interceptor + auto token refresh
- **ESLint + Prettier**

## Setup

```bash
cd frontend
npm install
cp .env.example .env   # adjust VITE_API_BASE_URL if needed
npm run dev            # http://localhost:5173/khamsk/
```

The dev server proxies `/api` to `http://localhost:8000` (the Django backend).
Start the backend first (`docker-compose up -d` from the project root).

## Scripts

| Command            | Description                          |
| ------------------ | ------------------------------------ |
| `npm run dev`      | Start dev server with HMR            |
| `npm run build`    | Production build to `dist/`          |
| `npm run preview`  | Preview the production build         |
| `npm run lint`     | Run ESLint                           |
| `npm run lint:fix` | Run ESLint with autofix              |
| `npm run format`   | Format with Prettier                 |

## Structure

```
src/
├── api/            # Axios instance + per-resource API modules
├── components/
│   ├── layout/     # AppLayout, AppSidebar, AppNavbar
│   └── common/     # Shared components (CompanyForm)
├── composables/    # useAuth
├── router/         # Routes + navigation guards
├── stores/         # Pinia stores (auth, patient, company)
└── views/          # Page components (auth, patients, companies, dashboard, error)
```

## Auth

- Login uses **email + password** → returns JWT access/refresh + user object.
- Access token stored in `localStorage`; refreshed automatically on 401.
- Users with `must_change_password` are forced to the change-password page.
- Sidebar menu items are role-scoped (admin, doctor, nurse, labtech, company_admin).

## Notes

- Backend contract references: patient list returns `company_detail`,
  company list returns `patient_count`, company packages live under
  `/api/companies/{id}/packages/` (nested route).
- Per-field pricing in the package assignment modal reads template
  `default_price` values; full per-field persistence lands in Sprint 6a.
