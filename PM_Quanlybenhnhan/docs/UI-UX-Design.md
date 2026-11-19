# UI/UX Design — Health Checkup Management System (AI Spec)

## Tech Stack

| Layer | Choice |
|-------|--------|
| Framework | Vue 3 (Composition API, `<script setup>`, TS) |
| Build | Vite |
| UI Library | PrimeVue 4 (DataTable, TabView, Dialog, Stepper, InputNumber, Calendar, Dropdown, Menu, Toast, ConfirmDialog, FileUpload) |
| Styling | Tailwind CSS (layout/spacing only) + PrimeVue theme tokens |
| State | Pinia |
| HTTP | Axios + JWT interceptor (access 15min, refresh 7d, auto-refresh on 401) |

---

## 1. Design Tokens

```ts
// tailwind.config.ts — extend theme
colors: {
  primary:       '#0A7C6E',  // Buttons, links, active tab, header
  'primary-dark':'#086B5E',
  secondary:     '#4A90D9',  // Info badges, loading
  success:       '#27AE60',  // Confirmed status, normal range
  warning:       '#F39C12',  // Draft status, borderline range
  danger:        '#E74C3C',  // Abnormal range, error, delete
  'bg-page':     '#F5F7FA',
  'text-body':   '#1A1A2E',
  'text-muted':  '#6B7280',
}
fontFamily: { sans: ['Inter', 'Be Vietnam Pro', 'sans-serif'] }
```

---

## 2. API Contracts (Backend Endpoints)

### 2.1 Auth

| Method | Path | Req | Res |
|--------|------|-----|-----|
| POST | `/api/auth/login/` | `{email, password}` | `{access, refresh, user}` |
| POST | `/api/auth/refresh/` | `{refresh}` | `{access}` |
| POST | `/api/auth/logout/` | `{refresh}` | `{}` |
| GET | `/api/auth/me/` | — | `User` |
| PUT | `/api/auth/change-password/` | `{old_password, new_password}` | `{}` |

### 2.2 Patients

| Method | Path | Req | Res |
|--------|------|-----|-----|
| GET | `/api/patients/` | `?search&company&page&page_size` | `Paginated<Patient>` |
| POST | `/api/patients/` | `PatientInput` | `Patient` |
| GET | `/api/patients/{id}/` | — | `PatientDetail` (incl. `examinations[]`) |
| PUT | `/api/patients/{id}/` | `PatientInput` | `Patient` |
| DELETE | `/api/patients/{id}/` | — | `204` (soft) |

### 2.3 Companies

| Method | Path | Req | Res |
|--------|------|-----|-----|
| GET | `/api/companies/` | `?search&page&page_size` | `Paginated<Company>` |
| POST | `/api/companies/` | `CompanyInput` | `Company` |
| GET | `/api/companies/{id}/` | — | `CompanyDetail` |
| PUT | `/api/companies/{id}/` | `CompanyInput` | `Company` |

### 2.4 Company Packages

| Method | Path | Req | Res |
|--------|------|-----|-----|
| GET | `/api/companies/{id}/packages/` | — | `CompanyExamPackage[]` |
| POST | `/api/companies/{id}/packages/` | `{exam_package_id, pricing_mode, total_employees}` | `CompanyExamPackage` |
| PUT | `/api/companies/{id}/packages/{pkg_id}/` | `{pricing_mode?, total_employees?, is_active?}` | `CompanyExamPackage` |
| GET | `/api/companies/{id}/packages/{pkg_id}/price-preview/` | — | `PricePreview` |

### 2.5 Departments & Templates

| Method | Path | Req | Res |
|--------|------|-----|-----|
| GET | `/api/departments/` | — | `Department[]` |
| GET | `/api/templates/` | `?department` | `DepartmentTemplate[]` |
| GET | `/api/templates/{id}/render/` | — | `{fields_config}` |

### 2.6 Exam Packages

| Method | Path | Req | Res |
|--------|------|-----|-----|
| GET | `/api/packages/` | — | `ExamPackage[]` |

### 2.7 Examinations

| Method | Path | Req | Res |
|--------|------|-----|-----|
| GET | `/api/examinations/` | `?patient&company&exam_type&status&date_from&date_to&page` | `Paginated<ExamListItem>` |
| POST | `/api/examinations/` | `{patient_id, company_exam_package_id?, exam_type, exam_date, doctor_id}` | `Examination` |
| GET | `/api/examinations/{id}/` | — | `ExaminationDetail` |
| PUT | `/api/examinations/{id}/` | `{conclusion?, disease_id?, status?}` | `Examination` |
| PATCH | `/api/examinations/{id}/status/` | `{status}` | `Examination` |
| DELETE | `/api/examinations/{id}/` | — | `204` (draft only) |
| GET | `/api/examinations/{id}/form/` | — | `FormData` |

### 2.8 Department Results

| Method | Path | Req | Res |
|--------|------|-----|-----|
| PUT | `/api/examinations/{exam_id}/departments/{dept_id}/` | `{data}` | `DepartmentResult` |
| PATCH | `/api/examinations/{exam_id}/departments/{dept_id}/complete/` | — | `DepartmentResult` |

### 2.9 Import

| Method | Path | Req | Res |
|--------|------|-----|-----|
| POST | `/api/examinations/import/{department_id}/` | `FormData (file)` | `ImportJob` |
| GET | `/api/import/{id}/status/` | — | `{status, progress, result}` |

### 2.10 Export

| Method | Path | Req | Res |
|--------|------|-----|-----|
| POST | `/api/export/` | `{company_id, package_id, department_id, exam_date?}` | `{export_id, status}` |
| GET | `/api/export/{id}/` | — | `{status, progress, download_url?}` |
| GET | `/api/export/{id}/download/` | — | `Blob (xlsx)` |

---

## 3. TypeScript Interfaces

```ts
// === Auth ===
interface User {
  id: string; full_name: string; email: string; role: Role;
  phone: string; company?: {id:string, name:string} | null;
  must_change_password: boolean;
}
type Role = 'admin' | 'doctor' | 'nurse' | 'labtech' | 'company_admin';
type Permission = 'admin' | 'doctor' | 'nurse_clinical' | 'labtech_paraclinical';

// === Patient ===
interface Patient {
  id: string; employee_code: string | null; full_name: string;
  dob: string; gender: 'male' | 'female'; cccd: string;
  phone: string; email: string; company: {id:string, name:string} | null;
  is_active: boolean;
}
interface PatientDetail extends Patient {
  examinations: ExamSummary[];
}

// === Company ===
interface Company {
  id: string; name: string; code: string; address: string;
  tax_code: string; contact_person: string; contact_phone: string;
  is_active: boolean;
}

// === Department ===
interface Department {
  id: string; name: string; code: string;
  category: 'clinical' | 'para_clinical';
}

// === Template & Field Definition ===
interface FieldDefinition {
  key: string; label: string;
  type: 'text' | 'number' | 'select' | 'multi-select' | 'boolean' | 'date';
  unit: string; required: boolean; order: number;
  normal_range?: { min: number | null; max: number | null };
  default_price: number; test_category: string;
  options?: {label:string, value:string}[];  // for select/multi-select
}
interface DepartmentTemplate {
  id: string; department: number; name: string;
  fields_config: FieldDefinition[]; version: number; is_active: boolean;
}

// === ExamPackage ===
interface ExamPackage {
  id: string; name: string; description: string;
  exam_type: ExamType; departments: Department[];
  default_package_price: number | null; is_active: boolean;
}
type ExamType = 'periodic' | 'occupational' | 'job_placement'
  | 'labor_under18' | 'labor_over18';

// === CompanyExamPackage ===
interface CompanyExamPackage {
  id: string; company: string; exam_package: ExamPackage;
  pricing_mode: 'per_field' | 'package_total';
  total_employees: number; is_active: boolean;
  assigned_at: string; assigned_by: string;
}
interface PricePreview {
  mode: 'per_field' | 'package_total';
  total_employees: number;
  cost_per_employee: number;
  grand_total: number;
}

// === Examination ===
interface ExamSummary {
  id: string; exam_date: string; exam_type: ExamType;
  status: ExamStatus; doctor_name: string;
}
type ExamStatus = 'draft' | 'completed' | 'confirmed';
interface ExamListItem extends ExamSummary {
  patient_name: string; employee_code: string | null;
  company_name: string; department_progress: string; // "3/5"
}
interface Examination {
  id: string; patient: Patient; company_exam_package: string | null;
  exam_type: ExamType; exam_date: string;
  conclusion: string; disease: string | null;
  doctor: string; status: ExamStatus; version: number;
}
interface ExaminationDetail extends Examination {
  department_results: DepartmentResultDetail[];
}
interface DepartmentResultDetail {
  id: string; department: Department;
  template_snapshot: FieldDefinition[];
  data: Record<string, any>;
  completed_by: string | null; completed_at: string | null;
  version: number;
}

// === Form Data (from /form/ endpoint) ===
interface FormData {
  examination: Examination;
  departments: FormDepartment[];
}
interface FormDepartment {
  department: Department; result_id: string;
  template_snapshot: FieldDefinition[];
  data: Record<string, any>;
  completed: boolean; editable: boolean;  // computed from role
}

// === Import ===
interface ImportJob {
  id: string; status: 'processing' | 'completed' | 'failed';
  progress: number; // 0-100
  result: { success: number; updated: number; skipped: number; errors: ImportError[] } | null;
}
interface ImportError { row: number; field: string; message: string; }
```

---

## 4. Business Rules

### 4.1 Status Workflow

```
draft ──(all departments filled + doctor conclusion)──▶ completed ──(doctor/admin confirms)──▶ confirmed
  │                                                                                                │
  └── deletable                                                                         immutable (Admin only)
```

### 4.2 Department-Level Permission

| Role | Departments can edit | Notes |
|------|---------------------|-------|
| `admin` | ALL | Passes `can_edit_department` without checking category |
| `doctor` | ALL | Same as admin for editing |
| `nurse` | `category='clinical'` | Runtime lookup from Department model |
| `labtech` | `category='para_clinical'` | Runtime lookup from Department model |
| `company_admin` | NONE | Cannot edit departments |

### 4.3 Patient Form Rules

- **Toggle**: "Có công ty" / "Cá nhân"
- `company` required when has_company=true
- `employee_code` required + unique per company when has_company=true
- `employee_code` hidden when has_company=false
- CCCD format: 9 or 12 digits, validated client-side

### 4.4 Pricing Rules

```
Per-field:   cost_per_employee = sum of all template field default_prices
             grand_total = cost_per_employee × total_employees
Package total: grand_total = default_package_price × total_employees
```

### 4.5 Package Assignment Rules

- `unique_together`: one active assignment per company-package pair
- Deactivation: `is_active=false` prevents new exams (existing unaffected)
- Fields computed from `ExamPackage → ExamPackageDepartment → DepartmentTemplate.fields_config`

---

## 5. Routes & Pages

```ts
const routes = [
  // Public
  { path: '/login',                    name: 'login',                    component: LoginPage },
  { path: '/change-password',          name: 'change-password',          component: ChangePasswordPage, meta: { requiresAuth: true } },

  // Auth-required (layout = AppLayout)
  { path: '/', component: AppLayout, meta: { requiresAuth: true }, children: [
    { path: '',                        name: 'dashboard',                component: DashboardPage },
    // Patients
    { path: 'patients',                name: 'patient-list',             component: PatientListPage },
    { path: 'patients/create',         name: 'patient-create',           component: PatientCreatePage },
    { path: 'patients/:id',            name: 'patient-detail',           component: PatientDetailPage },
    // Companies
    { path: 'companies',               name: 'company-list',             component: CompanyListPage },
    { path: 'companies/create',        name: 'company-create',           component: CompanyCreatePage },
    { path: 'companies/:id',           name: 'company-detail',           component: CompanyDetailPage },
    { path: 'companies/:id/packages',  name: 'company-packages',         component: CompanyPackagesPage },
    // Examinations
    { path: 'examinations',            name: 'exam-list',                component: ExamListPage },
    { path: 'examinations/create',     name: 'exam-create',              component: ExamCreatePage },
    { path: 'examinations/:id',        name: 'exam-detail',              component: ExamDetailPage },
    { path: 'examinations/:id/edit',   name: 'exam-edit',                component: ExamEditPage },
    // Import
    { path: 'import',                  name: 'import',                   component: ExcelImportPage },
    // Reports
    { path: 'reports',                 name: 'report-list',              component: ReportListPage },
    // Error
    { path: '/403',                    name: 'forbidden',                component: ForbiddenPage },
    { path: '/:pathMatch(.*)*',        name: 'not-found',                component: NotFoundPage },
  ]},
];
```

### Sidebar Menu Config

```ts
// Per-role menu (computed in AppSidebar.vue from useAuth().user.role)
const menuByRole: Record<Role, MenuItem[]> = {
  admin: [
    { label: 'Tổng quan',    icon: 'pi pi-home',          to: '/' },
    { label: 'Bệnh nhân',    icon: 'pi pi-users',         to: '/patients' },
    { label: 'Công ty',      icon: 'pi pi-building',      to: '/companies' },
    { label: 'Khám bệnh',    icon: 'pi pi-file-edit',     to: '/examinations' },
    { label: 'Nhập Excel',   icon: 'pi pi-upload',        to: '/import' },
    { label: 'Báo cáo',      icon: 'pi pi-chart-bar',     to: '/reports' },
  ],
  doctor: ['Tổng quan','Bệnh nhân','Khám bệnh','Nhập Excel'],
  nurse:  ['Tổng quan','Bệnh nhân','Khám bệnh','Nhập Excel'],
  labtech:['Tổng quan','Bệnh nhân','Khám bệnh','Nhập Excel'],
  company_admin: ['Tổng quan','Bệnh nhân'],
};
```

---

## 6. Component Specifications

### 6.1 Common Components (Pure — no store, no router)

```
ALL: defineProps + defineEmits only. No imports from stores/router.
     Use defineOptions({ inheritAttrs: false }) to pass attrs to root element.
```

| File | Props | Emits | Slots | Notes |
|------|-------|-------|-------|-------|
| `DataTable.vue` | `columns: ColumnDef[], data: any[], loading: boolean, paginator?: boolean, totalRecords?: number, rows?: number, sortable?: boolean, filterable?: boolean` | `page, sort, filter, row-click` | `#header, #body:{field}, #empty` | Wraps PrimeVue DataTable. ColumnDef = `{field, header, sortable?, filterable?, width?}` |
| `SearchBar.vue` | `modelValue: string, placeholder?: string` | `update:modelValue` | — | Input with 300ms debounce + clear button |
| `StatusBadge.vue` | `status: string, size?: 'sm'\|'md'` | — | — | `status → {severity, label}` map defined internally |
| `ConfirmDialog.vue` | `visible: boolean, title: string, message: string, confirmLabel?: string, danger?: boolean` | `confirm, cancel` | — | Wraps PrimeVue ConfirmDialog |
| `EmptyState.vue` | `icon?: string, title: string, description?: string, actionLabel?: string` | `action` | — | Centered illustration with optional CTA |
| `LoadingSkeleton.vue` | `rows?: number, cols?: number, type: 'table'\|'card'\|'form'` | — | — | Skeleton placeholders |
| `ActionMenu.vue` | `actions: {label, icon?, severity?, disabled?, handler}[]` | — | — | 3-dot dropdown menu |
| `PageHeader.vue` | `title: string, subtitle?: string` | — | `#actions` | Breadcrumb auto from useRoute() |
| `SectionCard.vue` | `title?: string, icon?: string` | — | `default` | White card with border, optional header |
| `FormField.vue` | `label: string, required?: boolean, error?: string, helpText?: string` | — | `default` | Label + error message wrapper |

### 6.2 Layout Components

| File | Structure | Behavior |
|------|-----------|----------|
| `AppLayout.vue` | `<AppTopbar/> <div class="flex"> <AppSidebar/> <main><router-view/></main> </div>` | Full height, sidebar fixed width 240px |
| `AppTopbar.vue` | `[Logo] Breadcrumb (left) / Avatar + Dropdown (right)` | Breadcrumb = useRoute().path → segments |
| `AppSidebar.vue` | `Menu items (role-filtered), collapsible` | `v-model:collapsed` from layout state, collapsed=64px, expanded=240px |

### 6.3 Feature Components (May use stores/composables)

**Patients:**
| File | Dependencies | Key Logic |
|------|-------------|-----------|
| `PatientForm.vue` | `FormField`, `Calendar` | Toggle hasCompany → show/hide employee_code |
| `PatientTable.vue` | `DataTable`, `StatusBadge`, `ActionMenu`, `SearchBar` | Columns vary by role; company filter |
| `PatientDetail.vue` | `SectionCard` | Personal info card + examination timeline |
| `ExaminationTimeline.vue` | — | Vertical timeline: icon(role) → date → status → conclusion |

**Companies:**
| File | Dependencies | Key Logic |
|------|-------------|-----------|
| `CompanyForm.vue` | `FormField` | Standard form |
| `CompanyTable.vue` | `DataTable`, `SearchBar` | Standard list |
| `CompanyDetail.vue` | `SectionCard` | Tabs: Employees \| Packages |
| `EmployeeListTab.vue` | `DataTable` | Read-only list of patients in company |
| `PackageList.vue` | `PackageCard` | Grid of cards |
| `PackageCard.vue` | `StatusBadge` | `props: pkg: CompanyExamPackage; emit: edit, deactivate` |

**Examinations (Core — complex):**

| File | Dependencies | Key Logic |
|------|-------------|-----------|
| `DynamicExamForm.vue` | `DepartmentTab[]`, `TabView` | Fetch `/form/` endpoint, manage activeTab, dirty state per tab |
| `DepartmentTab.vue` | `FieldTable` | `props: {department, templateSnapshot, data, editable, completed}` |
| `FieldTable.vue` | `TextField, NumberField, SelectField, ...` | Strategy pattern: `<component :is="renderers[field.type]" />` |
| `NormalRangeBadge.vue` | — | `props: {value, range}` → severity: success/warn/danger |
| `ConclusionSection.vue` | `FormField`, `Textarea`, `Dropdown` | Doctor conclusion + disease selector |
| `ExamStatusActions.vue` | — | `props: {status, role}` → show appropriate action buttons |
| `DepartmentProgress.vue` | — | `props: {total, completed}` → "3/5" text + bar |

**Field Renderers (all share same interface):**
```ts
// Each file under fields/:
interface FieldRendererProps {
  field: FieldDefinition;  // the FieldDefinition from template_snapshot
  modelValue: any;
}
// Emits: update:modelValue
```

| File | Component | Extra |
|------|-----------|-------|
| `TextField.vue` | `InputText` | — |
| `NumberField.vue` | `InputNumber` | Shows `NormalRangeBadge` beside input |
| `SelectField.vue` | `Dropdown` | `options` from `field.options` |
| `MultiSelectField.vue` | `MultiSelect` | `options` from `field.options` |
| `BooleanField.vue` | `ToggleButton` | — |
| `DateField.vue` | `Calendar` | `dateFormat="dd/mm/yy"` |

**Packages:**
| File | Dependencies | Key Logic |
|------|-------------|-----------|
| `PackageAssignmentModal.vue` | `PricingModeToggle`, `PricingFieldTable`, `Dialog` | Mode toggle switches table/price input |
| `PricingModeToggle.vue` | — | Radio group: per_field / package_total |
| `PricingFieldTable.vue` | `DataTable` | All fields from package departments, editable override prices |

**Import:**
| File | Dependencies | Key Logic |
|------|-------------|-----------|
| `ExcelImportWizard.vue` | `Stepper` | 4-step wizard |
| `ColumnMapper.vue` | `DataTable`, `Dropdown` | Auto-map by header name, manual override dropdown |
| `ImportResult.vue` | — | Success/error summary table |

---

## 7. Composable Specifications

```ts
// Each composable: pure function returning refs/computed/methods
useAuth(): { user: Ref<User | null>, login(email, password), logout(), refreshToken(), isAuthenticated: Computed<boolean>, hasRole(role: Role): boolean }
useApi(): { api: AxiosInstance }  // Singleton — base URL, JWT interceptor, auto-refresh
useToast(): { showSuccess(msg), showError(msg), showWarn(msg) }  // Wraps PrimeVue useToast()
useConfirm(): { require(title, message, danger?): Promise<boolean> }  // Wraps ConfirmDialog
useDebounce(value: Ref<T>, delay=300): Ref<T>
useRoleGuard(requiredRoles?: Role[], requiredCategory?: 'clinical'|'para_clinical'): { allowed: Computed<boolean>, permission: Computed<Permission> }
useExamForm(examId: Ref<string>): { form: Ref<FormData>, loading, saveTab(deptId, data), completeTab(deptId), dirtyTabs: Ref<Set<string>> }
usePricing(pkg: Ref<CompanyExamPackage>): { costPerEmployee, grandTotal }  // computed
useExport(templateId: Ref<number>): { downloadTemplate(), loading }
useBreadcrumb(): { items: Computed<BreadcrumbItem[]> }  // auto from route path
```

---

## 8. Pinia Store Schemas

```ts
// stores/auth.ts
interface AuthState {
  user: User | null; accessToken: string | null; refreshToken: string | null;
}
// Actions: login, logout, refreshToken, fetchMe, updateProfile

// stores/patients.ts
interface PatientState {
  list: Patient[]; current: PatientDetail | null; totalRecords: number;
  filters: { search: string; company: string | null; page: number; page_size: number };
}
// Actions: fetchList, fetchById, create, update, remove

// stores/companies.ts  — same pattern as patients
interface CompanyState {
  list: Company[]; current: CompanyDetail | null; totalRecords: number;
  filters: { search: string; page: number; page_size: number };
}

// stores/exams.ts
interface ExamState {
  list: ExamListItem[]; current: ExaminationDetail | null; formData: FormData | null;
  filters: { search: string; status: ExamStatus | null; date_from: string | null; date_to: string | null; page: number };
}
// Actions: fetchList, fetchById, fetchForm, create, update, updateStatus, remove

// stores/departments.ts
interface DepartmentState {
  list: Department[]; templates: Record<number, DepartmentTemplate>; // keyed by department id
}
// Actions: fetchDepartments, fetchTemplates(departmentId)

// stores/packages.ts
interface PackageState {
  examPackages: ExamPackage[]; companyPackages: Record<string, CompanyExamPackage[]>; // keyed by company id
}
// Actions: fetchExamPackages, fetchCompanyPackages(companyId), assignPackage, updatePackage, pricePreview

// stores/import.ts
interface ImportState {
  currentJob: ImportJob | null;
}
// Actions: startImport, pollStatus (setInterval), cancel
```

---

## 9. Page Layouts

### 9.1 List Page Pattern

```vue
<!-- Template for ALL list pages -->
<PageHeader :title="title">
  <template #actions>
    <Button :label="`+ Thêm ${entity}`" @click="router.push(createRoute)" />
  </template>
</PageHeader>
<SearchBar v-model="filters.search" :placeholder="`Tìm ${entity}...`" />
<DataTable :columns :data="list" :loading :total-records="totalRecords"
  @page="onPage" @sort="onSort" @row-click="onRowClick" />
```

### 9.2 Form Page Pattern

```vue
<!-- Template for ALL form pages -->
<PageHeader :title="isEdit ? `Sửa ${entity}` : `Thêm ${entity}`" />
<SectionCard>
  <FormField v-for="field in fields" :key="field.key" :label="field.label" :required="field.required" :error="errors[field.key]">
    <component :is="fieldComponents[field.type]" v-model="form[field.key]" />
  </FormField>
  <div class="flex gap-2 mt-4">
    <Button label="Lưu" @click="save" />
    <Button label="Hủy" severity="secondary" @click="router.back()" />
  </div>
</SectionCard>
```

### 9.3 Exam Form Page (DynamicExamForm)

```vue
<TabView v-model:activeIndex="activeTab">
  <TabPanel v-for="dept in formData.departments" :key="dept.department.id"
    :header="dept.department.name"
    :disabled="!dept.editable"
    :pt="{ headerAction: { class: { 'opacity-50': !dept.editable } } }">
    <DepartmentTab
      :department="dept.department"
      :template-snapshot="dept.template_snapshot"
      :data="dept.data"
      :editable="dept.editable"
      :completed="dept.completed"
      @save="saveDepartment" />
  </TabPanel>
</TabView>
<ConclusionSection v-if="isDoctor" v-model="conclusion" :editable="canEdit" />
<ExamStatusActions :status="examination.status" :role="user.role" @complete="completeExam" @confirm="confirmExam" />
```

---

## 10. Directory Structure (Generated by Vite)

```
frontend/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── src/
    ├── main.ts
    ├── App.vue
    ├── router/index.ts
    ├── stores/          (7 files — see §8)
    ├── composables/     (10 files — see §7)
    ├── services/        (8 files — one per domain, Axios calls only)
    ├── types/           (1 file: index.ts — all interfaces from §3)
    ├── components/
    │   ├── common/      (12 files — see §6.1)
    │   ├── layout/      (3 files — see §6.2)
    │   ├── patients/    (4 files)
    │   ├── companies/   (6 files)
    │   ├── examinations/(9 files + 6 in fields/)
    │   ├── packages/    (3 files)
    │   └── import/      (3 files)
    ├── pages/           (17 files — see §5)
    ├── assets/logo.svg
    └── styles/main.css
```

---

## 11. Build Priority (Iteration Order)

### Iteration 1 — Foundation
1. Scaffold project (Vite + Vue 3 + PrimeVue + Tailwind + Axios)
2. `types/index.ts` — all interfaces
3. `services/api.js` — Axios instance + JWT interceptor
4. `stores/auth.ts` + `composables/useAuth.ts`
5. `AppLayout`, `AppTopbar`, `AppSidebar`
6. `LoginPage`, `ChangePasswordPage`
7. `router/index.ts` (full route table + auth guard)

### Iteration 2 — Patient & Company CRUD
8. `DataTable`, `SearchBar`, `PageHeader`, `FormField`, `StatusBadge`, `ConfirmDialog`, `ActionMenu`, `EmptyState`, `LoadingSkeleton`, `SectionCard`
9. `stores/patients.ts`, `services/patients.ts`
10. `PatientTable`, `PatientForm`, `PatientDetail`, `ExaminationTimeline`
11. `PatientListPage`, `PatientCreatePage`, `PatientDetailPage`
12. Same for Companies (identical pattern)

### Iteration 3 — Examination Core
13. `stores/exams.ts`, `services/exams.ts`
14. `fields/*.vue` (6 field renderers)
15. `NormalRangeBadge`, `FieldTable`, `DepartmentTab`
16. `DynamicExamForm`, `ConclusionSection`, `ExamStatusActions`, `DepartmentProgress`
17. `ExamListPage`, `ExamCreatePage`, `ExamDetailPage`, `ExamEditPage`

### Iteration 4 — Packages & Import
18. `stores/packages.ts`, `services/packages.ts`
19. `PricingModeToggle`, `PricingFieldTable`, `PackageAssignmentModal`
20. `PackageList`, `PackageCard`
21. `CompanyPackagesPage`
22. `stores/import.ts`, `services/import.ts`
23. `ColumnMapper`, `ImportResult`, `ExcelImportWizard`
24. `ExcelImportPage`

### Iteration 5 — Polish
25. `DashboardPage` (stat cards + recent exams)
26. `ReportListPage` (placeholder)
27. Responsive tweaks
28. `ForbiddenPage`, `NotFoundPage`
