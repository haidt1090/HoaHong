<template>
  <div>
    <div class="mb-3 flex items-center justify-end gap-3">
      <div ref="searchWrap">
        <IconField>
          <InputIcon class="pi pi-search" />
          <InputText
            v-model="search"
            class="p-inputtext-sm"
            placeholder="Tìm kiếm..."
          />
        </IconField>
      </div>
      <Button
        label="Tải mẫu Excel"
        icon="pi pi-download"
        size="small"
        severity="secondary"
        outlined
        @click="downloadTemplate"
      />
      <Button
        label="Nhập Excel"
        icon="pi pi-upload"
        size="small"
        severity="secondary"
        outlined
        @click="importVisible = true"
      />
      <Button
        label="Thêm nhân viên"
        icon="pi pi-user-plus"
        size="small"
        outlined
        @click="router.push({ name: 'patient-create' })"
      />
      <Button
        label="Phím tắt"
        icon="pi pi-keyboard"
        size="small"
        severity="secondary"
        text
        @click="shortcutsVisible = true"
      />
    </div>

    <div v-if="selectedEmployees.length > 0" class="mb-2 flex items-center gap-2 rounded bg-primary/10 px-3 py-2 text-sm">
      <span>Đã chọn <strong>{{ selectedEmployees.length }}</strong> nhân viên</span>
      <div class="ml-auto flex gap-2">
        <Button label="Xác nhận" icon="pi pi-check-circle" size="small" severity="success" :loading="bulkLoading" @click="bulkConfirm" />
        <Button label="Hoàn thành" icon="pi pi-check" size="small" :loading="bulkLoading" @click="bulkComplete" />
        <Button label="Xóa" icon="pi pi-trash" size="small" severity="danger" :loading="bulkLoading" @click="bulkDelete" />
        <Button label="Bỏ chọn" icon="pi pi-times" size="small" severity="secondary" text @click="selectedEmployees = []" />
      </div>
    </div>

    <DataTable
      :key="`${sortField}-${sortOrder}`"
      :columns="columns"
      :data="filteredPatients"
      :loading="loading"
      :paginator="true"
      :rows="pageSize"
      :total-records="totalRecords"
      :row-class="rowClass"
      @page="onPage"
      @sort="onSort"
    >
      <template #body-employee_code="{ data }">
        <div class="flex items-center gap-2">
          <Checkbox
            :model-value="isSelected(data)"
            :binary="true"
            @click.stop
            @update:model-value="toggleSelect(data)"
          />
          <span>{{ data.employee_code || '--' }}</span>
        </div>
      </template>
      <template #header-employee_code>
        <div class="flex items-center gap-2">
          <Checkbox
            :model-value="isAllSelected"
            :binary="true"
            @update:model-value="toggleSelectAll"
          />
          <span>Mã NV</span>
        </div>
      </template>
      <template #body-full_name="{ data }">
        <span class="font-medium text-primary">{{ data.full_name }}</span>
      </template>
      <template #body-gender="{ value }">{{ genderLabel(value) }}</template>
      <template #body-progress="{ data }">
        <DepartmentProgress
          v-if="data._latestExam?.departments_completed != null"
          :completed="data._latestExam.departments_completed"
          :total="data._latestExam.departments_total"
        />
        <span v-else class="text-text-muted">--</span>
      </template>
      <template #body-status="{ data }">
        <StatusBadge v-if="data._latestExam?.status" :status="data._latestExam.status" size="sm" />
        <span v-else class="text-text-muted">--</span>
      </template>
      <template #actions="{ data }">
        <div class="flex gap-1">
          <Button
            v-tooltip.top="'Nhập liệu'"
            icon="pi pi-file-edit"
            size="small"
            severity="secondary"
            outlined
            @click.stop="onStartEntry(data)"
          />
          <Button
            v-if="data._latestExam"
            v-tooltip.top="'Sửa kết quả khám'"
            icon="pi pi-pencil"
            size="small"
            severity="secondary"
            text
            @click.stop="onEditExam(data)"
          />
          <Button
            v-if="data._latestExam"
            v-tooltip.top="'Xem kết quả'"
            icon="pi pi-eye"
            size="small"
            severity="info"
            text
            @click.stop="openReportUrl(data.id)"
          />
          <Button
            v-tooltip.top="'Xóa'"
            icon="pi pi-trash"
            size="small"
            severity="danger"
            text
            @click.stop="onDelete(data)"
          />
        </div>
      </template>
      <template #empty>
        <EmptyState icon="pi pi-users" title="Chưa có nhân viên" />
      </template>
    </DataTable>

    <EmployeeImportModal
      v-model:visible="importVisible"
      :company-id="companyId"
      @imported="refresh"
    />

    <ShortcutsModal v-model:visible="shortcutsVisible" :groups="EMPLOYEE_LIST_SHORTCUTS" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import InputText from 'primevue/inputtext'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import DataTable from '@/components/common/DataTable.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import DepartmentProgress from '@/components/examinations/DepartmentProgress.vue'
import EmployeeImportModal from '@/components/companies/EmployeeImportModal.vue'
import ShortcutsModal from '@/components/common/ShortcutsModal.vue'
import { patientsService } from '@/services/patients'
import { examsService } from '@/services/exams'
import { genderLabel } from '@/utils/format'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'
import { extractError } from '@/services/api'
import { EMPLOYEE_LIST_SHORTCUTS } from '@/shortcuts'
import type { ColumnDef, Patient, ExamListItem, ExamStatus } from '@/types'

const props = defineProps<{ companyId: string; active?: boolean }>()
const emit = defineEmits<{ 'start-entry': [patient: Patient] }>()
const router = useRouter()
const toast = useToast()
const confirm = useConfirm()

type PatientWithExam = Patient & { _latestExam?: ExamListItem }

const patients = ref<PatientWithExam[]>([])
const loading = ref(false)
const importVisible = ref(false)
const reportUrls = ref<Record<string, string>>({})
const search = ref('')
const selectedEmployees = ref<PatientWithExam[]>([])
const bulkLoading = ref(false)
const searchWrap = ref<HTMLElement | null>(null)
const shortcutsVisible = ref(false)
const highlightedIndex = ref(-1)

const filteredPatients = computed(() => {
  if (!search.value.trim()) return patients.value
  const q = search.value.toLowerCase()
  return patients.value.filter((p) =>
    (p.employee_code || '').toLowerCase().includes(q)
    || p.full_name.toLowerCase().includes(q)
    || (p.department || '').toLowerCase().includes(q),
  )
})

const pageSize = ref(20)
const currentPage = ref(0)
const totalRecords = ref(0)
const sortField = ref<string | null>(null)
const sortOrder = ref<1 | -1>(1)

watch([sortField, sortOrder], () => {
  currentPage.value = 0
  refresh()
})

function onPage(event: unknown): void {
  const e = event as { page: number; rows: number }
  currentPage.value = e.page
  pageSize.value = e.rows
  refresh()
}

function onSort(event: unknown) {
  const e = event as { sortField: string; sortOrder: number }
  sortField.value = e.sortField
  sortOrder.value = e.sortOrder === -1 ? -1 : 1
}

const columns: ColumnDef[] = [
  { field: 'employee_code', header: 'Mã NV', width: '8rem', sortable: true },
  { field: 'full_name', header: 'Họ tên', sortable: true },
  { field: 'dob', header: 'Ngày sinh', width: '10rem' },
  { field: 'gender', header: 'Giới tính', width: '8rem' },
  { field: 'department', header: 'Phòng ban', sortable: true },
  { field: 'progress', header: 'Tiến độ khám', width: '10rem', sortable: true },
  { field: 'status', header: 'Trạng thái', width: '9rem', sortable: true },
]

async function openReportUrl(patientId: string): Promise<void> {
  const cached = reportUrls.value[patientId]
  if (cached) {
    window.open(cached, '_blank')
    return
  }
  try {
    const { data } = await patientsService.reportLink(patientId)
    reportUrls.value[patientId] = data.url
    window.open(data.url, '_blank')
  } catch {
    // fallback: construct URL from latest exam if API fails
    const p = patients.value.find((x) => x.id === patientId)
    if (p?._latestExam) window.open(`/ket-qua/${p._latestExam.id}`, '_blank')
  }
}

watch(search, () => { currentPage.value = 0 })

watch(filteredPatients, () => {
  if (filteredPatients.value.length === 0) {
    highlightedIndex.value = -1
  } else if (highlightedIndex.value >= filteredPatients.value.length) {
    highlightedIndex.value = filteredPatients.value.length - 1
  }
})

function onStartEntry(data: unknown): void {
  emit('start-entry', data as Patient)
}

function rowClass(data: unknown): string | undefined {
  const p = data as PatientWithExam
  const highlighted = filteredPatients.value[highlightedIndex.value]
  return highlighted && highlighted.id === p.id ? 'bg-primary/10' : undefined
}

function moveSelection(direction: 1 | -1): void {
  const len = filteredPatients.value.length
  if (len === 0) return
  if (highlightedIndex.value < 0) {
    highlightedIndex.value = direction === 1 ? 0 : len - 1
  } else {
    highlightedIndex.value = Math.min(Math.max(highlightedIndex.value + direction, 0), len - 1)
  }
}

function selectedPatient(): PatientWithExam | null {
  if (highlightedIndex.value < 0) return null
  return filteredPatients.value[highlightedIndex.value] ?? null
}

function openSelected(): void {
  const p = selectedPatient()
  if (p) onStartEntry(p)
}

async function deleteSelected(): Promise<void> {
  const p = selectedPatient()
  if (p) await onDelete(p)
}

function focusSearch(): void {
  nextTick(() => {
    const input = searchWrap.value?.querySelector('input') as HTMLElement | null
    input?.focus()
  })
}

function isSelected(data: unknown): boolean {
  return selectedEmployees.value.some((p) => p.id === (data as PatientWithExam).id)
}

function toggleSelect(data: unknown): void {
  const patient = data as PatientWithExam
  const idx = selectedEmployees.value.findIndex((p) => p.id === patient.id)
  if (idx >= 0) {
    selectedEmployees.value = selectedEmployees.value.filter((_, i) => i !== idx)
  } else {
    selectedEmployees.value = [...selectedEmployees.value, patient]
  }
}

const isAllSelected = computed(() =>
  filteredPatients.value.length > 0 && filteredPatients.value.every((p) => isSelected(p)),
)

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedEmployees.value = []
  } else {
    selectedEmployees.value = [...filteredPatients.value]
  }
}

function onEditExam(data: unknown): void {
  const patient = data as PatientWithExam
  if (patient._latestExam) {
    const url = router.resolve({ name: 'exam-edit', params: { id: patient._latestExam.id } }).href
    window.open(url, '_blank')
  }
}

async function onDelete(data: unknown): Promise<void> {
  const patient = data as Patient
  const yes = await confirm.require(
    'Xóa nhân viên',
    `Bạn có chắc muốn xóa ${patient.full_name}?`,
  )
  if (!yes) return
  try {
    await patientsService.remove(patient.id)
    toast.showSuccess('Đã xóa nhân viên')
    refresh()
  } catch (err) {
    toast.showError(extractError(err, 'Không thể xóa'))
  }
}

async function bulkUpdateStatus(status: ExamStatus): Promise<void> {
  const count = selectedEmployees.value.length
  const label = status === 'confirmed' ? 'Xác nhận' : 'Hoàn thành'
  const ok = await confirm.require(
    `${label} hàng loạt`,
    `${label} lượt khám gần nhất của ${count} nhân viên đã chọn?`,
  )
  if (!ok) return

  bulkLoading.value = true
  let success = 0
  let fail = 0
  for (const p of selectedEmployees.value) {
    const exam = p._latestExam as (ExamListItem & { status: string }) | undefined
    if (!exam || exam.status === status) continue
    try {
      await examsService.updateStatus(exam.id, status)
      exam.status = status
      success++
    } catch {
      fail++
    }
  }
  bulkLoading.value = false
  selectedEmployees.value = []
  if (fail === 0) {
    toast.showSuccess(`Đã ${label.toLowerCase()} ${success} lượt khám`)
  } else {
    toast.showWarn(`${label} ${success} lượt, ${fail} lỗi`)
  }
}

function bulkConfirm(): Promise<void> { return bulkUpdateStatus('confirmed') }
function bulkComplete(): Promise<void> { return bulkUpdateStatus('completed') }

async function bulkDelete(): Promise<void> {
  const count = selectedEmployees.value.length
  const ok = await confirm.require(
    'Xóa nhân viên',
    `Xóa ${count} nhân viên đã chọn? Hành động không thể hoàn tác.`,
    true,
  )
  if (!ok) return

  bulkLoading.value = true
  let success = 0
  let fail = 0
  const toDelete = [...selectedEmployees.value]
  for (const p of toDelete) {
    try {
      await patientsService.remove(p.id)
      patients.value = patients.value.filter((x) => x.id !== p.id)
      success++
    } catch {
      fail++
    }
  }
  bulkLoading.value = false
  selectedEmployees.value = []
  if (fail === 0) {
    toast.showSuccess(`Đã xóa ${success} nhân viên`)
  } else {
    toast.showWarn(`Đã xóa ${success} nhân viên, ${fail} lỗi`)
  }
}

async function downloadTemplate(): Promise<void> {
  try {
    const { data } = await patientsService.downloadTemplate()
    const url = window.URL.createObjectURL(data as Blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'employee_import_template.xlsx'
    a.click()
    window.URL.revokeObjectURL(url)
  } catch {
    toast.showError('Không thể tải mẫu Excel')
  }
}

async function refresh(): Promise<void> {
  loading.value = true
  try {
    const page = currentPage.value + 1
    const ORDERING_MAP: Record<string, string> = {
      status: 'exam_status',
      progress: 'exam_progress',
    }
    const orderingField = ORDERING_MAP[sortField.value ?? ''] ?? sortField.value
    const ordering = sortField.value ? `${sortOrder.value === -1 ? '-' : ''}${orderingField}` : undefined
    const patResp = await patientsService.list({
      company: props.companyId,
      is_active: true,
      page,
      page_size: pageSize.value,
      ordering,
    })
    const rawPatients: Patient[] = Array.isArray(patResp.data.results)
      ? patResp.data.results
      : (patResp.data as unknown as Patient[])
    totalRecords.value = (patResp.data as { count?: number }).count ?? rawPatients.length

    // Fetch exams only for displayed patients
    const patientIds = rawPatients.map((p) => p.id)
    const examMap = new Map<string, ExamListItem>()
    if (patientIds.length > 0) {
      const examResults = await Promise.allSettled(
        patientIds.map((pid) => examsService.list({ patient: pid, company: props.companyId, page_size: 1 })),
      )
      for (const result of examResults) {
        if (result.status === 'fulfilled') {
          const exams: ExamListItem[] = Array.isArray(result.value.data.results)
            ? result.value.data.results
            : (result.value.data as unknown as ExamListItem[])
          for (const exam of exams) {
            const pid = (exam as ExamListItem & { patient?: string }).patient
            if (pid && !examMap.has(pid)) {
              const raw = exam as ExamListItem & {
                patient?: string
                department_results?: {
                  template_snapshot?: { key: string }[]
                  data?: Record<string, unknown>
                }[]
              }
              const results = raw.department_results ?? []
              let filled = 0
              let totalFields = 0
              for (const r of results) {
                const fields = r.template_snapshot ?? []
                totalFields += fields.length
                const data = r.data ?? {}
                for (const f of fields) {
                  const v = data[f.key]
                  if (v !== null && v !== undefined && v !== '') filled++
                }
              }
              examMap.set(pid, {
                ...exam,
                departments_completed: filled,
                departments_total: totalFields,
                department_progress: totalFields > 0 ? `${Math.round((filled / totalFields) * 100)}%` : '0%',
              })
            }
          }
        }
      }
    }

    try {
      const { data: links } = await patientsService.reportLinks(props.companyId)
      const urls: Record<string, string> = {}
      for (const [pid, info] of Object.entries(links)) {
        urls[pid] = info.url
      }
      reportUrls.value = urls
    } catch {
      reportUrls.value = {}
    }

    patients.value = rawPatients.map((p) => ({
      ...p,
      _latestExam: examMap.get(p.id),
    }))
  } finally {
    loading.value = false
  }
}

onMounted(refresh)

const shortcuts = useKeyboardShortcuts()
const isActive = () => props.active !== false

shortcuts.register('Ctrl+F', () => focusSearch(), { preventDefault: true, when: isActive })
shortcuts.register('ArrowDown', () => moveSelection(1), { preventDefault: true, when: isActive })
shortcuts.register('ArrowUp', () => moveSelection(-1), { preventDefault: true, when: isActive })
shortcuts.register('Enter', () => openSelected(), { preventDefault: true, when: isActive })
shortcuts.register('Delete', () => deleteSelected(), { preventDefault: true, when: isActive })
</script>
