import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { examsService, type ExamListParams } from '@/services/exams'
import type {
  ExaminationInput,
  ExamListItem,
  ExaminationDetail,
  ExamFormData,
  ExamStatus,
  ExamType,
  DepartmentResultInput,
  FieldDefinition,
} from '@/types'

interface ExamFilters {
  search: string
  company: string | null
  status: ExamStatus | null
  exam_type: ExamType | null
  date_from: string | null
  date_to: string | null
  page: number
  page_size: number
}

// --- Backend -> frontend normalization ------------------------------------
// The backend Examination list serializer returns nested patient/doctor objects
// and a `department_results[]` array rather than the flat ExamListItem shape the
// UI expects. Normalize here so pages can rely on a stable contract.

interface RawDeptResult {
  completed_at?: string | null
  template_snapshot?: { key: string }[]
  data?: Record<string, unknown>
}

interface RawExamRow {
  id: string
  patient?: string
  patient_name?: string
  patient_detail?: { employee_code?: string | null; company_detail?: { name?: string } }
  employee_code?: string | null
  company_name?: string
  exam_type: ExamType
  exam_date: string
  doctor?: string | null
  doctor_name?: string
  status: ExamStatus
  department_results?: RawDeptResult[]
  department_progress?: { done: number; total: number } | string
}

function normalizeListItem(row: RawExamRow): ExamListItem {
  const results = row.department_results ?? []
  // Progress = filled field values / total fields across all department results
  let done = 0
  let total = 0
  for (const r of results) {
    const fields = r.template_snapshot ?? []
    total += fields.length
    const data = r.data ?? {}
    for (const f of fields) {
      const v = data[f.key]
      if (v !== null && v !== undefined && v !== '') done++
    }
  }
  if (total === 0 && row.department_progress && typeof row.department_progress === 'object') {
    done = row.department_progress.done
    total = row.department_progress.total
  }
  return {
    id: row.id,
    patient_name: row.patient_name ?? '',
    employee_code: row.employee_code ?? null,
    company_name: row.company_name ?? '',
    exam_type: row.exam_type,
    exam_date: row.exam_date,
    doctor_name: row.doctor_name ?? '',
    status: row.status,
    department_progress: total > 0 ? `${Math.round((done / total) * 100)}%` : '0%',
    departments_completed: done,
    departments_total: total,
  }
}

interface RawFormDept {
  result_id: string
  department: { id: string; name: string; code: string; category: 'clinical' | 'para_clinical' }
  editable: boolean
  template_id?: string | null
  template_snapshot: unknown[]
  data: Record<string, unknown>
  completed_at?: string | null
}

interface RawFormResponse {
  id: string
  status: ExamStatus
  exam_type: ExamType
  consultation: string
  conclusion: string
  work_fitness: string
  patient_gender?: string | null
  departments: RawFormDept[]
}

function normalizeForm(raw: RawFormResponse): ExamFormData {
  return {
    examination: {
      id: raw.id,
      patient: '',
      company_exam_package: null,
      exam_type: raw.exam_type,
      exam_date: '',
      consultation: raw.consultation ?? '',
      conclusion: raw.conclusion,
      work_fitness: (raw.work_fitness as ExamFormData['examination']['work_fitness']) ?? 'pending',
      classification: null,
      disease: '',
      doctor: null,
      status: raw.status,
      version: 1,
    },
    patient_gender: (raw.patient_gender as ExamFormData['patient_gender']) ?? null,
    departments: (raw.departments ?? []).map((d) => ({
      department: {
        id: d.department.id,
        name: d.department.name,
        code: d.department.code,
        category: d.department.category,
      },
      result_id: d.result_id,
      template_id: d.template_id ?? null,
      template_snapshot: d.template_snapshot as FieldDefinition[],
      data: d.data ?? {},
      completed: d.completed_at != null,
      editable: d.editable,
    })),
  }
}

export const useExamStore = defineStore('exams', () => {
  const list = ref<ExamListItem[]>([])
  const current = ref<ExaminationDetail | null>(null)
  const formData = ref<ExamFormData | null>(null)
  const totalRecords = ref(0)
  const loading = ref(false)

  const filters = reactive<ExamFilters>({
    search: '',
    company: null,
    status: null,
    exam_type: null,
    date_from: null,
    date_to: null,
    page: 1,
    page_size: 20,
  })

  async function fetchList(): Promise<void> {
    loading.value = true
    try {
      const params: ExamListParams = {
        search: filters.search || undefined,
        company: filters.company || undefined,
        status: filters.status || undefined,
        exam_type: filters.exam_type || undefined,
        date_from: filters.date_from || undefined,
        date_to: filters.date_to || undefined,
        page: filters.page,
        page_size: filters.page_size,
      }
      const { data } = await examsService.list(params)
      const rows = (data.results ?? []) as unknown as RawExamRow[]
      list.value = rows.map(normalizeListItem)
      totalRecords.value = data.count ?? list.value.length
    } finally {
      loading.value = false
    }
  }

  async function fetchById(id: string): Promise<ExaminationDetail> {
    loading.value = true
    try {
      const { data } = await examsService.get(id)
      current.value = data
      return data
    } finally {
      loading.value = false
    }
  }

  async function fetchForm(id: string): Promise<ExamFormData> {
    loading.value = true
    try {
      const { data } = await examsService.getForm(id)
      const normalized = normalizeForm(data as unknown as RawFormResponse)
      formData.value = normalized
      return normalized
    } finally {
      loading.value = false
    }
  }

  async function create(payload: ExaminationInput): Promise<ExaminationDetail> {
    const { data } = await examsService.create(payload)
    return data as unknown as ExaminationDetail
  }

  async function update(id: string, payload: Partial<ExaminationDetail>): Promise<void> {
    const { data } = await examsService.update(id, payload)
    current.value = data as unknown as ExaminationDetail
  }

  async function updateStatus(id: string, status: ExamStatus): Promise<void> {
    const { data } = await examsService.updateStatus(id, status)
    current.value = data as unknown as ExaminationDetail
  }

  async function remove(id: string): Promise<void> {
    await examsService.remove(id)
    list.value = list.value.filter((e) => e.id !== id)
  }

  async function saveDepartmentResult(
    examId: string,
    deptId: string,
    data: Record<string, unknown>,
  ): Promise<void> {
    const payload: DepartmentResultInput = { data }
    await examsService.updateDepartmentResult(examId, deptId, payload)
  }

  async function completeDepartmentResult(examId: string, deptId: string): Promise<void> {
    await examsService.completeDepartmentResult(examId, deptId)
  }

  function resetFilters(): void {
    filters.search = ''
    filters.company = null
    filters.status = null
    filters.exam_type = null
    filters.date_from = null
    filters.date_to = null
    filters.page = 1
  }

  return {
    list,
    current,
    formData,
    totalRecords,
    loading,
    filters,
    fetchList,
    fetchById,
    fetchForm,
    create,
    update,
    updateStatus,
    remove,
    saveDepartmentResult,
    completeDepartmentResult,
    resetFilters,
  }
})
