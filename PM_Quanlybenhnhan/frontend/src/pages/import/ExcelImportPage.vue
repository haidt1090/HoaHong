<template>
  <div>
    <PageHeader title="Nhập / Xuất dữ liệu" subtitle="Nhập kết quả khám và danh sách nhân viên từ file Excel" />

    <Tabs v-model:value="activeTab">
      <TabList>
        <Tab value="exam-data">Nhập dữ liệu khám</Tab>
        <Tab value="employees">Nhập nhân viên</Tab>
        <Tab value="templates">Nhập dữ liệu mẫu</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="exam-data">
          <SectionCard>
      <!-- Row 1: Company + Package + Department -->
      <div class="mb-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        <FormField label="Công ty" required>
          <Select
            v-model="selectedCompany"
            :options="companies"
            option-label="name"
            option-value="id"
            placeholder="-- Chọn công ty --"
            filter
            show-clear
            fluid
            @update:model-value="onCompanyChanged"
          />
        </FormField>
        <FormField label="Gói khám" required>
          <Select
            v-model="selectedPackage"
            :options="companyPackages"
            option-label="label"
            option-value="value"
            placeholder="-- Chọn gói khám --"
            filter
            fluid
            :disabled="!selectedCompany"
            @update:model-value="onPackageChanged"
          />
        </FormField>
        <FormField label="Mẫu nhập liệu" required>
          <Select
            v-model="selectedTemplateId"
            :options="templateOptions"
            option-label="label"
            option-value="value"
            placeholder="-- Chọn mẫu --"
            fluid
            :disabled="!selectedPackage"
            @update:model-value="onTemplateSelected"
          />
        </FormField>
      </div>

      <div v-if="selectedDepartmentTemplate" class="mb-4 text-sm text-text-muted">
        {{ selectedDepartmentTemplate.fields_config?.length ?? 0 }} chỉ số —
        Phòng ban: <strong>{{ selectedDeptName }}</strong>
      </div>

      <!-- Row 2: Export mode + Export button (no exam date — scoped by active package) -->
      <div class="mb-4 flex flex-wrap items-end gap-4">
        <FormField v-if="selectedTemplateId" label="Chế độ xuất" class="w-40">
          <Select
            v-model="exportMode"
            :options="exportModeOptions"
            option-label="label"
            option-value="value"
            fluid
          />
        </FormField>
        <div v-if="selectedTemplateId" class="flex items-end gap-2 pb-1">
          <template v-if="exportStatus === 'idle'">
            <Button
              label="Xuất Excel"
              icon="pi pi-download"
              severity="secondary"
              outlined
              @click="startExport"
            />
          </template>
          <template v-else-if="exportStatus === 'processing'">
            <Button
              :label="exportProgress ? `Đang tạo... ${exportProgress}` : 'Đang tạo...'"
              icon="pi pi-spinner pi-spin"
              severity="secondary"
              disabled
            />
          </template>
          <template v-else-if="exportStatus === 'done'">
            <Button
              label="Tải xuống"
              icon="pi pi-download"
              severity="success"
              @click="downloadExport"
            />
          </template>
          <template v-else-if="exportStatus === 'failed'">
            <Button
              label="Thử lại"
              icon="pi pi-refresh"
              severity="danger"
              text
              @click="startExport"
            />
            <span class="text-xs text-danger">Lỗi tạo file</span>
          </template>
        </div>
      </div>

      <!-- Import: exam date applies only when uploading, not when exporting -->
      <div class="mb-4">
        <FormField label="Ngày khám (khi nhập)" class="w-48">
          <DatePicker v-model="examDate" date-format="dd/mm/yy" show-icon fluid />
        </FormField>
      </div>

      <!-- Row 3: File upload -->
      <div class="mb-4">
        <label class="mb-1 block text-sm font-medium text-text-body">File Excel (.xlsx, .xls)</label>
        <div
          class="rounded-lg border-2 border-dashed p-6 text-center transition-colors"
          :class="dragOver ? 'border-primary bg-primary/5' : 'border-gray-300'"
          @dragover.prevent="dragOver = true"
          @dragleave.prevent="dragOver = false"
          @drop.prevent="onDrop"
        >
          <i class="pi pi-file-excel text-3xl text-green-600" />
          <p class="mt-1 text-sm text-text-muted">Kéo thả file Excel vào đây hoặc click để chọn</p>
          <label class="mt-1 inline-block cursor-pointer font-medium text-primary hover:underline">
            Chọn file
            <input type="file" accept=".xlsx,.xls" class="hidden" @change="onFileSelect" />
          </label>
          <p v-if="selectedFile" class="mt-1 text-sm font-medium text-success">
            {{ selectedFile.name }} ({{ formatSize(selectedFile.size) }})
          </p>
        </div>
      </div>

      <!-- Row 4: Column mapping preview -->
      <div v-if="columnMappings.length > 0" class="mb-4">
        <h4 class="mb-2 text-sm font-semibold text-text-body">Ánh xạ cột</h4>
        <div class="overflow-x-auto rounded-lg border border-gray-200">
          <table class="w-full border-collapse text-sm">
            <thead>
              <tr class="border-b border-gray-200 bg-gray-50">
                <th class="px-3 py-2 text-left">Cột trong file</th>
                <th class="px-3 py-2 text-left">Ánh xạ tới</th>
                <th class="px-3 py-2 text-center">Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in columnMappings" :key="m.excelColumn" class="border-b border-gray-100">
                <td class="px-3 py-2 font-mono text-xs">{{ m.excelColumn }}</td>
                <td class="px-3 py-2">
                  <Select
                    v-model="m.targetKey"
                    :options="fieldOptions"
                    option-label="label"
                    option-value="value"
                    placeholder="-- Chọn --"
                    show-clear
                    size="small"
                    class="w-56"
                  />
                </td>
                <td class="px-3 py-2 text-center">
                  <Tag :value="m.matched ? 'Đã khớp' : 'Chưa khớp'" :severity="m.matched ? 'success' : 'warn'" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Import button -->
      <div class="flex items-center gap-3">
        <Button
          label="Bắt đầu nhập"
          icon="pi pi-upload"
          :loading="importStore.importing"
          :disabled="!canImport"
          @click="onStartImport"
        />
        <span v-if="importProgress" class="text-sm text-text-muted">{{ importProgress }}</span>
      </div>

      <!-- Import result -->
      <div v-if="importStore.currentJob" class="mt-4 rounded-lg border border-gray-200 p-4">
        <h4 class="mb-3 text-base font-semibold text-text-body">Kết quả nhập</h4>
        <div class="mb-4 grid grid-cols-4 gap-4">
          <div class="rounded-lg bg-gray-50 p-3 text-center">
            <p class="text-2xl font-bold text-text-body">{{ importStore.currentJob.total_rows ?? 0 }}</p>
            <p class="text-xs text-text-muted">Tổng dòng</p>
          </div>
          <div class="rounded-lg bg-green-50 p-3 text-center">
            <p class="text-2xl font-bold text-success">{{ importStore.currentJob.success_count ?? 0 }}</p>
            <p class="text-xs text-text-muted">Thành công</p>
          </div>
          <div class="rounded-lg bg-blue-50 p-3 text-center">
            <p class="text-2xl font-bold text-secondary">{{ importStore.currentJob.updated_count ?? 0 }}</p>
            <p class="text-xs text-text-muted">Cập nhật</p>
          </div>
          <div class="rounded-lg bg-yellow-50 p-3 text-center">
            <p class="text-2xl font-bold text-warning">{{ importStore.currentJob.skipped_count ?? 0 }}</p>
            <p class="text-xs text-text-muted">Bỏ qua</p>
          </div>
        </div>

        <div v-if="importStore.currentJob.errors?.length" class="mt-3">
          <h5 class="mb-2 text-sm font-semibold text-danger">
            Chi tiết lỗi ({{ importStore.currentJob.errors.length }})
          </h5>
          <div class="max-h-60 overflow-y-auto rounded-lg border border-gray-200">
            <table class="w-full border-collapse text-sm">
              <thead class="sticky top-0">
                <tr class="border-b border-gray-200 bg-red-50">
                  <th class="px-3 py-2 text-left">Dòng</th>
                  <th class="px-3 py-2 text-left">Mã NV</th>
                  <th class="px-3 py-2 text-left">Mô tả lỗi</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(err, i) in importStore.currentJob.errors" :key="i" class="border-b border-gray-100">
                  <td class="px-3 py-2">{{ err.row ?? '--' }}</td>
                  <td class="px-3 py-2 font-mono text-xs">{{ err.employee_code ?? err.field ?? '--' }}</td>
                  <td class="px-3 py-2 text-danger">{{ err.message }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="mt-4 flex gap-2">
          <Button label="Nhập file khác" severity="secondary" @click="onReset" />
          <Button label="Về danh sách khám" icon="pi pi-arrow-left" @click="router.push({ name: 'exam-list' })" />
        </div>
      </div>
    </SectionCard>
          </TabPanel>
          <TabPanel value="employees">
            <EmployeeImportTab />
          </TabPanel>
          <TabPanel value="templates">
            <GenericImportTab :templates="dataTemplates" />
          </TabPanel>
        </TabPanels>
      </Tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import Tag from 'primevue/tag'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import FormField from '@/components/common/FormField.vue'
import EmployeeImportTab from '@/pages/import/EmployeeImportTab.vue'
import GenericImportTab from '@/pages/import/GenericImportTab.vue'
import type { TemplateOption } from '@/pages/import/GenericImportTab.vue'
import { companiesService } from '@/services/companies'
import { departmentsService } from '@/services/departments'
import { packagesService } from '@/services/packages'
import { importService } from '@/services/import'
import { diagnosisService } from '@/services/diagnosis'
import { useImportStore } from '@/stores/import'
import { useToast } from '@/composables/useToast'
import { extractError } from '@/services/api'
import { examTypeLabel } from '@/utils/format'
import * as XLSX from 'xlsx'
import type { Company, DepartmentTemplate, ExamType } from '@/types'

const FIXED_COLUMNS = [
  { label: 'Mã NV', key: '_employee_code' },
  { label: 'Họ tên', key: '_full_name' },
]

const dataTemplates: TemplateOption[] = [
  {
    key: 'benh_tu_van',
    label: 'Bệnh & Tư Vấn',
    description: 'Nhập mã bệnh và từ khóa chẩn đoán từ file Excel.',
    downloadFn: () => diagnosisService.downloadKeywordTemplate() as Promise<{ data: Blob }>,
    importFn: (file: File) => diagnosisService.importKeywords(file, 'append') as Promise<{ data: Record<string, number | unknown[]> }>,
    resultFields: [
      { key: 'diseases_created', label: 'Bệnh đã tạo' },
      { key: 'keywords_created', label: 'Từ khóa đã tạo' },
    ],
  },
]

const router = useRouter()
const importStore = useImportStore()
const toast = useToast()

const companies = ref<Company[]>([])
const activeTab = ref('exam-data')
const selectedCompany = ref<string | null>(null)
const companyPackages = ref<{ label: string; value: string; examType: ExamType; packageId: string }[]>([])
const selectedPackage = ref<string | null>(null)
const selectedPackageId = ref<string | null>(null)
const templateOptions = ref<{ label: string; value: string; deptId: string }[]>([])
const selectedTemplateId = ref<string | null>(null)
const selectedDepartmentTemplate = ref<DepartmentTemplate | null>(null)
const selectedDepartment = ref<string | null>(null)
const selectedDeptName = ref('')
const examDate = ref<Date>(new Date())
const selectedFile = ref<File | null>(null)
const dragOver = ref(false)
const columnMappings = ref<{ excelColumn: string; targetKey: string; matched: boolean }[]>([])
const importProgress = ref<string | null>(null)

const exportStatus = ref<'idle' | 'processing' | 'done' | 'failed'>('idle')
const exportId = ref<string | null>(null)
const exportProgress = ref<string | null>(null)
const exportMode = ref<'all' | 'pending'>('all')
const exportModeOptions = [
  { label: 'Tất cả nhân viên', value: 'all' },
  { label: 'Chưa hoàn thành', value: 'pending' },
]
let exportPollTimer: ReturnType<typeof setInterval> | null = null

const canImport = computed(() =>
  selectedCompany.value && selectedPackage.value && selectedTemplateId.value && selectedFile.value,
)

const fieldOptions = computed(() => {
  const fields = selectedDepartmentTemplate.value?.fields_config ?? []
  return [
    { label: '-- Bỏ qua --', value: '' },
    ...FIXED_COLUMNS.map((c) => ({ label: c.label, value: c.key })),
    ...fields.map((f) => ({ label: f.label, value: f.key })),
  ]
})

function formatSize(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(0)} KB`
}

function toLocalISODate(value: Date): string {
  const y = value.getFullYear()
  const m = String(value.getMonth() + 1).padStart(2, '0')
  const d = String(value.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

onMounted(() => loadCompanies())

async function loadCompanies() {
  const { data } = await companiesService.list({ page_size: 200 })
  const raw = data as { results?: Company[] }
  companies.value = raw.results || (data as unknown as Company[])
}

async function onCompanyChanged() {
  selectedPackage.value = null
  selectedTemplateId.value = null
  selectedDepartmentTemplate.value = null
  selectedFile.value = null
  columnMappings.value = []
  resetExport()
  if (!selectedCompany.value) {
    companyPackages.value = []
    templateOptions.value = []
    return
  }
  try {
    const { data } = await packagesService.listCompanyPackages(selectedCompany.value)
    const result = Array.isArray(data) ? data : (data as { results: unknown[] }).results || []
    companyPackages.value = (result as Array<{ id: string; is_active: boolean; package_detail: { name: string; exam_type: ExamType }; exam_package: string }>)
      .filter((cp) => cp.is_active)
      .map((cp) => ({
        label: `${cp.package_detail?.name ?? cp.exam_package} (${examTypeLabel(cp.package_detail?.exam_type)})`,
        value: cp.id,
        examType: cp.package_detail?.exam_type,
        packageId: cp.exam_package,
      }))
  } catch {
    companyPackages.value = []
  }
}

async function onPackageChanged() {
  selectedTemplateId.value = null
  selectedDepartmentTemplate.value = null
  resetExport()
  const pkg = companyPackages.value.find((p) => p.value === selectedPackage.value)
  selectedPackageId.value = pkg?.packageId ?? null
  if (!selectedPackageId.value) {
    templateOptions.value = []
    return
  }
  try {
    const { data: pkgData } = await packagesService.getExamPackage(selectedPackageId.value)
    const bindings = pkgData.package_departments ?? []
    const opts: { label: string; value: string; deptId: string }[] = []
    for (const b of bindings) {
      let tplName = b.template
      try {
        const { data: tpl } = await departmentsService.getTemplate(b.template)
        tplName = tpl.name ?? b.template
      } catch { /* use ID */ }
      opts.push({
        label: `${tplName} (${b.department_detail?.name ?? ''})`,
        value: b.template,
        deptId: b.department,
      })
    }
    templateOptions.value = opts
  } catch {
    templateOptions.value = []
  }
}

async function onTemplateSelected() {
  if (!selectedTemplateId.value) {
    selectedDepartment.value = null
    selectedDepartmentTemplate.value = null
    selectedDeptName.value = ''
    return
  }
  resetExport()
  try {
    const { data: tpl } = await departmentsService.getTemplate(selectedTemplateId.value)
    selectedDepartmentTemplate.value = tpl
    selectedDeptName.value = tpl.department_detail?.name ?? ''
    const opt = templateOptions.value.find((o) => o.value === selectedTemplateId.value)
    if (opt) selectedDepartment.value = opt.deptId
  } catch {
    selectedDepartmentTemplate.value = null
    selectedDeptName.value = ''
  }
}

// --- File ---
function onDrop(event: DragEvent) {
  dragOver.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) setFile(file)
}

function onFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) setFile(file)
}

function setFile(file: File) {
  if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
    toast.showError('Vui lòng chọn file Excel (.xlsx hoặc .xls)')
    return
  }
  selectedFile.value = file
  columnMappings.value = []
  importProgress.value = null
  // Auto-analyze
  analyzeFile(file)
}

function analyzeFile(file: File) {
  const templateFields = selectedDepartmentTemplate.value?.fields_config ?? []
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const data = new Uint8Array(e.target!.result as ArrayBuffer)
      const workbook = XLSX.read(data, { type: 'array' })
      const sheet = workbook.Sheets[workbook.SheetNames[0]]
      const json = XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1 })
      const headerRow = (json[0] ?? []) as string[]

      const mappings: { excelColumn: string; targetKey: string; matched: boolean }[] = []
      const usedKeys = new Set<string>()
      const allColumns = [
        ...FIXED_COLUMNS.map((c) => ({ label: c.label, key: c.key })),
        ...templateFields.map((f) => ({ label: f.label, key: f.key })),
      ]

      for (const col of headerRow) {
        const colStr = String(col).trim()
        if (!colStr) continue
        const match = allColumns.find(
          (c) => c.label.trim().toLowerCase() === colStr.toLowerCase() && !usedKeys.has(c.key),
        )
        const key = match ? match.key : ''
        if (key) usedKeys.add(key)
        mappings.push({ excelColumn: colStr, targetKey: key, matched: !!key })
      }

      for (const col of allColumns) {
        if (!usedKeys.has(col.key)) {
          mappings.push({ excelColumn: col.label, targetKey: col.key, matched: true })
        }
      }
      columnMappings.value = mappings
    } catch {
      toast.showError('Không thể đọc file Excel.')
    }
  }
  reader.readAsArrayBuffer(file)
}

// --- Export ---
function resetExport() {
  if (exportPollTimer) clearInterval(exportPollTimer)
  exportStatus.value = 'idle'
  exportId.value = null
  exportProgress.value = null
}

async function startExport() {
  if (!selectedCompany.value || !selectedPackageId.value || !selectedDepartment.value) return
  resetExport()
  exportStatus.value = 'processing'
  try {
    const { data } = await importService.startExport({
      company_id: selectedCompany.value,
      package_id: selectedPackageId.value,
      department_id: selectedDepartment.value,
      mode: exportMode.value,
    })
    exportId.value = data.id
    exportPollTimer = setInterval(async () => {
      if (!exportId.value) return
      try {
        const { data: status } = await importService.getExportStatus(exportId.value)
        if (status.progress && typeof status.progress === 'object') {
          exportProgress.value = `${status.progress.current}/${status.progress.total}`
        }
        if (status.status === 'completed') {
          clearInterval(exportPollTimer!)
          exportPollTimer = null
          exportStatus.value = 'done'
        } else if (status.status === 'failed') {
          clearInterval(exportPollTimer!)
          exportPollTimer = null
          exportStatus.value = 'failed'
          toast.showError('Không thể tạo file xuất')
        }
      } catch {
        clearInterval(exportPollTimer!)
        exportPollTimer = null
        exportStatus.value = 'failed'
      }
    }, 1500)
  } catch {
    exportStatus.value = 'failed'
  }
}

async function downloadExport() {
  if (!exportId.value) return
  try {
    const response = await importService.downloadExport(exportId.value)
    const url = window.URL.createObjectURL(response.data as Blob)
    const a = document.createElement('a')
    a.href = url
    const disposition = (response.headers as Record<string, string>)['content-disposition'] ?? ''
    const match = disposition.match(/filename="?([^"]+)"?/)
    a.download = match?.[1] ?? 'export.xlsx'
    a.click()
    window.URL.revokeObjectURL(url)
  } catch {
    toast.showError('Không thể tải file')
  }
}

// --- Import ---
async function onStartImport() {
  if (!selectedFile.value || !selectedDepartment.value || !selectedCompany.value || !selectedPackageId.value) return

  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('company_id', selectedCompany.value)
  formData.append('exam_package_id', selectedPackageId.value!)
  formData.append('exam_date', toLocalISODate(examDate.value))

  try {
    await importStore.startImport(selectedDepartment.value, formData)
    if (importStore.currentJob?.id) {
      const poll = setInterval(async () => {
        await importStore.pollStatus(importStore.currentJob!.id)
        const job = importStore.currentJob
        if (job) {
          importProgress.value = `${job.success_count ?? 0}/${job.total_rows ?? 0}`
        }
        if (!job || job.status === 'completed' || job.status === 'failed') {
          clearInterval(poll)
          importProgress.value = null
        }
      }, 1500)
    }
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi nhập liệu'))
  }
}

function onReset() {
  if (exportPollTimer) clearInterval(exportPollTimer)
  importStore.reset()
  selectedFile.value = null
  columnMappings.value = []
  exportStatus.value = 'idle'
  exportProgress.value = null
  importProgress.value = null
}
</script>
