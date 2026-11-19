<template>
  <SectionCard>
    <p class="mb-4 text-sm text-text-muted">{{ templateConfig.description }}</p>

    <!-- Row 1: Template selector + Download -->
    <div class="mb-4 flex flex-wrap items-end gap-4">
      <FormField label="Mẫu" required class="w-64">
        <Select
          v-model="selectedTemplate"
          :options="templates"
          option-label="label"
          option-value="key"
          placeholder="-- Chọn mẫu --"
          fluid
        />
      </FormField>
      <div class="flex items-end gap-2 pb-1">
        <Button
          label="Tải mẫu Excel"
          icon="pi pi-download"
          severity="secondary"
          outlined
          :disabled="!selectedTemplate"
          @click="downloadTemplate"
        />
      </div>
    </div>

    <!-- File upload -->
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
    </div>

    <!-- Result -->
    <div v-if="result" class="mt-4 rounded-lg border border-gray-200 p-4">
      <h4 class="mb-3 text-base font-semibold text-text-body">Kết quả nhập</h4>
      <div class="mb-4 grid gap-4" :class="resultCols">
        <div v-for="stat in resultStats" :key="stat.label" class="rounded-lg p-3 text-center" :class="stat.bgClass">
          <p class="text-2xl font-bold" :class="stat.textClass">{{ stat.value }}</p>
          <p class="text-xs text-text-muted">{{ stat.label }}</p>
        </div>
      </div>
      <div class="mt-4">
        <Button label="Nhập file khác" severity="secondary" @click="onReset" />
      </div>
    </div>
  </SectionCard>
</template>

<script setup lang="ts">
import { ref, computed, type PropType } from 'vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import SectionCard from '@/components/common/SectionCard.vue'
import FormField from '@/components/common/FormField.vue'
import { useToast } from '@/composables/useToast'
import { extractError } from '@/services/api'

export interface TemplateOption {
  key: string
  label: string
  description: string
  downloadFn: () => Promise<{ data: Blob }>
  importFn: (file: File) => Promise<{ data: Record<string, number | unknown[]> }>
  resultFields: { key: string; label: string }[]
}

const props = defineProps({
  templates: { type: Array as PropType<TemplateOption[]>, required: true },
})

const toast = useToast()

const selectedTemplate = ref<string | null>(null)
const selectedFile = ref<File | null>(null)
const dragOver = ref(false)
const importing = ref(false)
const result = ref<Record<string, number | unknown[]> | null>(null)

const templateConfig = computed(() =>
  props.templates.find((t) => t.key === selectedTemplate.value) ?? { description: '', importFn: () => Promise.resolve({ data: {} }), resultFields: [], downloadFn: () => Promise.resolve({ data: new Blob() }) } as unknown as TemplateOption,
)

const resultStats = computed(() => {
  if (!result.value) return []
  return templateConfig.value.resultFields.map((f) => ({
    label: f.label,
    value: result.value![f.key] ?? 0,
    bgClass: '',
    textClass: 'text-text-body',
  }))
})

const resultCols = computed(() => {
  const n = templateConfig.value.resultFields.length
  if (n <= 2) return 'grid-cols-2'
  if (n <= 3) return 'grid-cols-3'
  return 'grid-cols-4'
})

const canImport = computed(() => selectedTemplate.value && selectedFile.value)

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
    const response = await templateConfig.value.downloadFn()
    const url = window.URL.createObjectURL(response.data as Blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedTemplate.value}_template.xlsx`
    a.click()
    window.URL.revokeObjectURL(url)
  } catch {
    toast.showError('Không thể tải mẫu')
  }
}

async function onStartImport() {
  if (!selectedFile.value || !selectedTemplate.value) return
  importing.value = true
  result.value = null
  try {
    const { data } = await templateConfig.value.importFn(selectedFile.value)
    result.value = data as Record<string, number | unknown[]>
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi nhập liệu'))
  } finally {
    importing.value = false
  }
}

function onReset() {
  selectedFile.value = null
  result.value = null
}
</script>
