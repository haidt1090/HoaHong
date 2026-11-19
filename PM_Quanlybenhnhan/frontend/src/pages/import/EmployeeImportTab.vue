<template>
  <SectionCard>
    <p class="mb-4 text-sm text-text-muted">
      Nhập danh sách nhân viên vào công ty từ file Excel. Tải mẫu bên dưới, điền dữ liệu rồi upload lại.
      Nếu công ty đang có gói khám active, hệ thống tự tạo phiếu khám và điền giá trị mặc định / ngẫu nhiên trong khoảng bình thường.
    </p>

    <!-- Row 1: Company + Download template -->
    <div class="mb-4 flex flex-wrap items-end gap-4">
      <FormField label="Công ty" required class="w-64">
        <Select
          v-model="selectedCompany"
          :options="companies"
          option-label="name"
          option-value="id"
          placeholder="-- Chọn công ty --"
          filter
          show-clear
          fluid
        />
      </FormField>
      <div class="flex items-end gap-2 pb-1">
        <Button
          label="Tải mẫu Excel"
          icon="pi pi-download"
          severity="secondary"
          outlined
          @click="downloadTemplate"
        />
      </div>
    </div>

    <!-- Row 2: File upload -->
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

    <!-- Import button -->
    <div class="flex items-center gap-3">
      <Button
        label="Bắt đầu nhập"
        icon="pi pi-upload"
        :loading="importing"
        :disabled="!canImport"
        @click="onStartImport"
      />
      <span v-if="importProgress" class="text-sm text-text-muted">{{ importProgress }}</span>
    </div>

    <!-- Import result -->
    <div v-if="result" class="mt-4 rounded-lg border border-gray-200 p-4">
      <h4 class="mb-3 text-base font-semibold text-text-body">Kết quả nhập</h4>
      <div class="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div class="rounded-lg bg-green-50 p-3 text-center">
          <p class="text-2xl font-bold text-success">{{ result.created ?? 0 }}</p>
          <p class="text-xs text-text-muted">Đã tạo NV</p>
        </div>
        <div class="rounded-lg bg-teal-50 p-3 text-center">
          <p class="text-2xl font-bold text-primary">{{ result.examinations_created ?? 0 }}</p>
          <p class="text-xs text-text-muted">Phiếu khám</p>
        </div>
        <div class="rounded-lg bg-blue-50 p-3 text-center">
          <p class="text-2xl font-bold text-secondary">{{ result.updated ?? 0 }}</p>
          <p class="text-xs text-text-muted">Đã cập nhật</p>
        </div>
        <div class="rounded-lg bg-yellow-50 p-3 text-center">
          <p class="text-2xl font-bold text-warning">{{ result.skipped ?? 0 }}</p>
          <p class="text-xs text-text-muted">Bỏ qua</p>
        </div>
      </div>

      <div v-if="result.errors?.length" class="mt-3">
        <h5 class="mb-2 text-sm font-semibold text-danger">Chi tiết lỗi ({{ result.errors.length }})</h5>
        <div class="max-h-60 overflow-y-auto rounded-lg border border-gray-200">
          <table class="w-full border-collapse text-sm">
            <thead class="sticky top-0">
              <tr class="border-b border-gray-200 bg-red-50">
                <th class="px-3 py-2 text-left">Dòng</th>
                <th class="px-3 py-2 text-left">Mô tả lỗi</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(err, i) in result.errors" :key="i" class="border-b border-gray-100">
                <td class="px-3 py-2">{{ err.row ?? '--' }}</td>
                <td class="px-3 py-2 text-danger">{{ err.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="mt-4">
        <Button label="Nhập file khác" severity="secondary" @click="onReset" />
      </div>
    </div>
  </SectionCard>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import SectionCard from '@/components/common/SectionCard.vue'
import FormField from '@/components/common/FormField.vue'
import { companiesService } from '@/services/companies'
import { patientsService } from '@/services/patients'
import { useToast } from '@/composables/useToast'
import { extractError } from '@/services/api'
import type { Company } from '@/types'

const toast = useToast()

const companies = ref<Company[]>([])
const selectedCompany = ref<string | null>(null)
const selectedFile = ref<File | null>(null)
const dragOver = ref(false)
const importing = ref(false)
const importProgress = ref<string | null>(null)

interface ImportResult {
  created: number
  updated: number
  skipped: number
  examinations_created: number
  errors: { row: number; message: string }[]
}
const result = ref<ImportResult | null>(null)

const canImport = computed(() => selectedCompany.value && selectedFile.value)

onMounted(() => loadCompanies())

async function loadCompanies() {
  try {
    const { data } = await companiesService.list({ page_size: 500 })
    const raw = data as { results?: Company[] }
    companies.value = raw.results || (data as unknown as Company[])
  } catch { /* ignore */ }
}

function formatSize(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(0)} KB`
}

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
  result.value = null
}

async function downloadTemplate() {
  try {
    const response = await patientsService.downloadTemplate()
    const url = window.URL.createObjectURL(response.data as Blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'employee_import_template.xlsx'
    a.click()
    window.URL.revokeObjectURL(url)
  } catch {
    toast.showError('Không thể tải mẫu')
  }
}

async function onStartImport() {
  if (!selectedFile.value || !selectedCompany.value) return

  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('company_id', selectedCompany.value)

  importing.value = true
  result.value = null
  try {
    const { data } = await patientsService.import(formData)
    result.value = {
      created: (data as Record<string, number>).created ?? 0,
      updated: (data as Record<string, number>).updated ?? 0,
      skipped: (data as Record<string, number>).skipped ?? 0,
      examinations_created: (data as Record<string, number>).examinations_created ?? 0,
      errors: (data as Record<string, unknown[]>).errors as ImportResult['errors'] ?? [],
    }
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi nhập liệu'))
  } finally {
    importing.value = false
    importProgress.value = null
  }
}

function onReset() {
  selectedFile.value = null
  result.value = null
}
</script>
