// ===========================================================================
// Shared TypeScript interfaces — mirrors backend DRF serializers.
// See docs/UI-UX-Design.md §3 and the Django serializers under src/.
// ===========================================================================

// === Common ===
export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// === Auth ===
export type Role = 'admin' | 'doctor' | 'nurse' | 'labtech' | 'company_admin'

export interface CompanyRef {
  id: string
  name: string
  code?: string
}

export interface User {
  id: string
  full_name: string
  email: string
  role: Role
  phone: string
  company?: CompanyRef | null
  is_active: boolean
  must_change_password: boolean
}

export interface LoginResponse {
  access: string
  refresh: string
  user: User
}

// === Patient ===
export type Gender = 'M' | 'F'

export interface Patient {
  id: string
  company: string | null
  company_detail: CompanyRef | null
  employee_code: string | null
  full_name: string
  dob: string
  gender: Gender
  cccd: string
  cccd_issued_date: string | null
  cccd_issued_place: string
  address: string
  phone: string
  email: string
  department: string
  start_date: string | null
  is_active: boolean
  notes: string
  created_at?: string
  updated_at?: string
}

export interface ExamSummary {
  id: string
  exam_date: string
  exam_type: ExamType
  status: ExamStatus
  conclusion: string
}

export interface PatientDetail extends Patient {
  examinations: ExamSummary[]
}

export interface PatientReportLink {
  url: string
  password: string
  exam_date: string
}

export interface PatientInput {
  company?: string | null
  employee_code?: string
  full_name: string
  dob: string
  gender: Gender | ''
  cccd?: string
  cccd_issued_date?: string | null
  cccd_issued_place?: string
  address?: string
  phone?: string
  email?: string
  department?: string
  start_date?: string | null
  notes?: string
}

// === Company ===
export interface Company {
  id: string
  name: string
  code: string
  address: string
  tax_code: string
  contact_person: string
  contact_phone: string
  contact_email: string
  is_active: boolean
  patient_count?: number
  created_at?: string
  updated_at?: string
}

export type CompanyDetail = Company

export interface CompanyInput {
  name: string
  code?: string
  address?: string
  tax_code?: string
  contact_person?: string
  contact_phone?: string
  contact_email?: string
  is_active?: boolean
}

// === Department & Template ===
export type DepartmentCategory = 'clinical' | 'para_clinical'

export interface Department {
  id: string
  name: string
  code: string
  category: DepartmentCategory
  description?: string
  is_active?: boolean
}

export interface NormalRange {
  min: number | null
  max: number | null
}

export interface GenderOverride {
  min?: number | null
  max?: number | null
  /** Random seed step; omitted → 0.1 when gender min/max apply. */
  step?: number | null
}

export interface GenderOverrides {
  M?: GenderOverride
  F?: GenderOverride
}

export interface FieldOption {
  label: string
  value: string
}

export interface FieldDefinition {
  key: string
  label: string
  type: 'text' | 'number' | 'select' | 'multi-select' | 'boolean' | 'date' | 'textarea' | 'computed'
  unit?: string
  required?: boolean
  order?: number
  normal_range?: NormalRange
  default_value?: unknown
  default_price?: number
  test_category?: string
  options?: FieldOption[]
  placeholder?: string
  formula?: string
  /** Client/server input rewrite; e.g. ``bp_slash`` turns 11280 into 112/80. */
  input_format?: 'bp_slash' | string
  /** Limit the field to one gender; omitted / ``all`` = everyone. */
  applies_to?: 'all' | Gender
  gender_overrides?: GenderOverrides
}

export interface ExamPackageDepartmentBinding {
  id: string
  department: string
  department_detail: Department
  template: string
  order: number
}

export interface DepartmentTemplate {
  id: string
  department: string
  department_detail?: Department
  name: string
  fields_config: FieldDefinition[]
  version: number
  is_active: boolean
}

// === ExamPackage ===
export type ExamType =
  'periodic' | 'occupational' | 'job_placement' | 'labor_under18' | 'labor_over18'

export interface ExamPackage {
  id: string
  name: string
  description: string
  exam_type: ExamType
  default_package_price: number | null
  is_active: boolean
  package_departments?: ExamPackageDepartmentBinding[]
}

export interface ExamPackageSummary {
  id: string
  name: string
  exam_type: ExamType
  default_package_price: number | null
  is_active: boolean
}

// === CompanyExamPackage ===
export type PricingMode = 'per_field' | 'package_total'

export interface CompanyExamPackage {
  id: string
  company: CompanyRef
  exam_package: string
  package_detail: ExamPackageSummary
  pricing_mode: PricingMode
  total_employees: number
  total_cost: number
  is_active: boolean
  assigned_at: string
  assigned_by: string | null
}

export interface CompanyExamPackageInput {
  exam_package: string
  pricing_mode: PricingMode
  total_employees: number
  is_active?: boolean
}

export interface PricePreview {
  mode: PricingMode
  total_employees: number
  cost_per_employee: number
  grand_total: number
}

// === Examination ===
export type ExamStatus = 'draft' | 'completed' | 'confirmed'

export interface ExamListItem {
  id: string
  patient_name: string
  employee_code: string | null
  company_name: string
  exam_date: string
  exam_type: ExamType
  doctor_name: string
  status: ExamStatus
  department_progress: string // "3/5"
  departments_completed: number
  departments_total: number
  total_departments?: number // count from exam_package (current, not snapshot)
}

export type WorkFitness = 'pending' | 'fit' | 'unfit'

export interface Examination {
  id: string
  patient: string
  patient_name?: string
  patient_detail?: Patient
  company_exam_package: string | null
  company_exam_package_detail?: CompanyExamPackage
  exam_type: ExamType
  exam_date: string
  conclusion: string
  consultation: string
  work_fitness: WorkFitness
  classification: number | null
  disease: string
  doctor: string | null
  doctor_name?: string
  status: ExamStatus
  version: number
  created_at?: string
  updated_at?: string
}

export interface ExaminationDetail extends Examination {
  department_results: DepartmentResultDetail[]
}

export interface DepartmentResultDetail {
  id: string
  department: string
  department_detail: Department
  template_snapshot: FieldDefinition[]
  data: Record<string, unknown>
  completed_by: string | null
  completed_at: string | null
  version: number
}

export interface ExaminationInput {
  patient: string
  company_exam_package?: string | null
  exam_type: ExamType
  exam_date: string
  doctor?: string | null
}

export interface DepartmentResultInput {
  data: Record<string, unknown>
}

// === Form Data (from /form/ endpoint) ===
export interface ExamFormData {
  examination: Examination
  departments: FormDepartment[]
  patient_gender?: Gender | null
}

export interface FormDepartment {
  department: Department
  result_id: string
  template_id: string | null
  template_snapshot: FieldDefinition[]
  data: Record<string, unknown>
  fields_table?: Array<{ key?: string; value?: unknown }>
  completed: boolean
  editable: boolean
  order?: number
}

// === Disease ===
export interface DiagnosisKeyword {
  id: string
  keyword: string
  disease_name: string
  conclusion_template: string
  classification: number | null
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface DiagnosisKeywordInput {
  keyword: string
  disease_name?: string
  conclusion_template?: string
  classification?: number | null
  is_active?: boolean
}

export interface FindingsResponse {
  findings: string
}

// -- Diagnosis Match (server-side keyword matching) --

export interface DiagnosisMatch {
  keyword: string
  disease_name: string
  conclusion_template: string
  classification: number | null
}

export interface DiagnosisResponse {
  matches: DiagnosisMatch[]
  classification: number | null
}

// Phân loại sức khỏe — Loại I→V (1→5), matching backend DiagnosisKeyword.CLASSIFICATION_*
export const DiagnosisClassification = {
  GOOD: 1,     // Loại I — rất tốt
  MILD: 2,     // Loại II — tốt
  DISEASE: 3,  // Loại III — trung bình
  POOR: 4,     // Loại IV — kém
  UNFIT: 5,    // Loại V — rất kém (không đủ ĐK lao động)
} as const

// === Import ===
export type ImportStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface ImportJob {
  id: string
  department: string
  department_name?: string
  exam_date: string
  status: ImportStatus
  total_rows: number
  success_count: number
  updated_count: number
  skipped_count: number
  errors: ImportError[]
  created_by?: string | null
  created_by_name?: string
  started_at?: string | null
  completed_at?: string | null
}

export interface ImportError {
  row: number
  employee_code?: string
  field?: string
  message: string
}

// === Report ===
export type ReportType = 'clinical_detail' | 'company_summary' | 'occupational' | 'cost'
export type ReportOutputFormat = 'xlsx' | 'html'
export type ReportStatus = 'processing' | 'done' | 'failed'

export interface Report {
  id: string
  company: string
  company_name?: string
  exam_package_name?: string
  report_type: ReportType
  output_format: ReportOutputFormat
  template: string | null
  template_name?: string | null
  status: ReportStatus
  parameters: Record<string, unknown>
  file_url: string | null
  error_message: string
  created_by: string | null
  created_by_name?: string
  created_at: string
  updated_at: string
}

export interface GenerateReportInput {
  company_id: string
  exam_package_id: string
  exam_date?: string
  report_type: ReportType
  output_format: ReportOutputFormat
  template_id?: string | null
  use_default_template?: boolean
}

// === Report templates (Sprint 9a) ===
export type ReportBodyType =
  | 'department_templates'
  | 'clinical_detail_table'
  | 'clinical_detail_blood_test'
  | 'summary_stats'
  | 'cost_breakdown'

export type ReportPageSize = 'A4 portrait' | 'A4 landscape' | 'A3 landscape'

/** Lightweight shape returned by the list endpoint (dropdowns). */
export interface ReportTemplateSummary {
  id: string
  name: string
  description: string
  report_type: ReportType
  body_type: ReportBodyType
  page_size: ReportPageSize
  is_default: boolean
  is_active: boolean
  item_count?: number
}

export interface ReportTemplateItem {
  id?: string
  department_template: string
  department_template_name?: string
  department: string | null
  exam_template?: string | null
  resolved_department?: string | null
  order: number
  page_break_before: boolean
}

export interface ReportTemplate extends ReportTemplateSummary {
  header_xlsx: string | null
  footer_xlsx: string | null
  body_config: Record<string, unknown>
  extra_css: string
  logo: string | null
  logo_url: string
  items: ReportTemplateItem[]
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface DepartmentReportTemplate {
  id: string
  name: string
  department: string | null
  department_name?: string
  body_html: string
  config: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface TemplateVariable {
  token: string
  label: string
}

export interface TemplateVariableGroup {
  group: string
  variables: TemplateVariable[]
}

export interface TemplateVariablesResponse {
  groups: TemplateVariableGroup[]
  body_types: { value: ReportBodyType; label: string }[]
  available_body_functions: string[]
}

export interface TemplatePreviewInput {
  company_id?: string | null
  exam_package_id?: string | null
  exam_date?: string | null
  limit?: number
  output_format?: 'html'
  body_html?: string
  department_id?: string | null
}

// === National Health Portal Sync (P8-S16) ===
export type SyncEnvironment = 'sandbox' | 'production'
export type SyncScopeType = 'company' | 'patient'
export type SyncJobStatus = 'pending' | 'processing' | 'done' | 'failed'

export interface SyncConfig {
  id: string
  environment: SyncEnvironment
  environment_display: string
  api_base_url: string
  api_base_url_effective: string
  username: string
  facility_code: string
  sender_id: string
  receiver_id: string
  version: string
  public_key: string
  is_active: boolean
  is_configured: boolean
  password_set: boolean
  private_key_set: boolean
  created_at?: string
  updated_at?: string
}

export type SyncConfigMap = Partial<Record<SyncEnvironment, SyncConfig>>

export interface SyncConfigInput {
  environment: SyncEnvironment
  api_base_url?: string
  username?: string
  password?: string
  facility_code?: string
  sender_id?: string
  receiver_id?: string
  version?: string
  private_key?: string
  public_key?: string
  is_active?: boolean
}

export interface SyncExamSummary {
  id: string
  patient: string
  /** Concluding doctor display name; empty when unset. */
  doctor: string
  exam_date: string
  status: ExamStatus
}

/** @deprecated Use SyncExamSummary */
export type SyncIncompleteExam = SyncExamSummary

export interface SyncValidationResult {
  total: number
  eligible: number
  eligible_exams: SyncExamSummary[]
  already_synced_count?: number
  already_synced?: SyncExamSummary[]
  /** @deprecated Status no longer blocks sync; always empty. */
  incomplete: SyncExamSummary[]
  /** Empty. The doctor signs later on the portal. */
  signature_issues?: string[]
  /** Distinct concluding doctors among exams still waiting to sync. */
  concluding_doctor_count?: number
}

export interface SyncTriggerInput {
  environment: SyncEnvironment
  scope_type: SyncScopeType
  company_id?: string | null
  patient_id?: string | null
  examination_id?: string | null
  /** Exam id → Base64(XML Signature) written into CKS_BENH_VIEN. */
  cks_nguoi_ket_luan?: Record<string, string>
}

export interface SyncSigningExam {
  id: string
  xml: string
}

export interface SyncSigningXmlResult {
  exams: SyncSigningExam[]
}

export interface SyncJob {
  id: string
  status: SyncJobStatus
  status_display: string
  environment: string
  environment_display: string
  scope_type: SyncScopeType
  scope_type_display: string
  company: string | null
  company_name: string | null
  patient: string | null
  patient_name: string | null
  examination: string | null
  examination_patient: string | null
  examination_count: number
  success_count: number
  failed_count: number
  skipped_count: number
  synced_examination_ids?: string[]
  response: Record<string, unknown>
  error_message: string
  created_by: string | null
  created_by_name: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

// === UI helpers ===
export interface ColumnDef {
  field: string
  header: string
  sortable?: boolean
  filterable?: boolean
  width?: string
}

export interface MenuItemDef {
  label: string
  icon: string
  to: string
  visible?: boolean
  /** Highlight only when the path matches exactly (not a longer child route). */
  exact?: boolean
}

export type DoctorSignatureKind = '' | 'image' | 'base64'

export interface DoctorSignatureRow {
  id: string
  full_name: string
  email: string
  signature_kind: DoctorSignatureKind
}

export interface ActionDef {
  label: string
  icon?: string
  severity?: string
  disabled?: boolean
  handler: () => void
}
