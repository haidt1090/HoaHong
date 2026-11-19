<template>
  <Dialog
    :visible="visible"
    header="Nhập danh sách nhân viên từ Excel"
    :style="{ width: '560px' }"
    modal
    @update:visible="$emit('update:visible', $event)"
  >
    <div class="flex flex-col gap-4">
      <!-- Step 1: Upload -->
      <div
        class="flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-gray-300 p-6 text-center transition-colors hover:border-primary"
        :class="{ 'bg-gray-50': !isDragOver, 'bg-primary/5 border-primary': isDragOver }"
        @dragover.prevent="isDragOver = true"
        @dragleave.prevent="isDragOver = false"
        @drop.prevent="onDrop"
      >
        <i class="pi pi-file-excel text-3xl text-gray-400" />
        <p v-if="!file" class="text-sm text-text-muted">
          Kéo thả file Excel (.xlsx, .csv) vào đây hoặc click để chọn
        </p>
        <p v-else class="text-sm font-medium text-primary">
          {{ file.name }} ({{ formatSize(file.size) }})
        </p>
        <input
          ref="fileInput"
          type="file"
          accept=".xlsx,.csv"
          class="hidden"
          @change="onInputChange"
        />
        <Button v-if="!file" label="Chọn file" size="small" outlined @click="fileInput?.click()" />
        <Button v-else label="Chọn file khác" size="small" outlined severity="secondary" @click="clearFile" />
      </div>

      <!-- Step 2: Result -->
      <div v-if="result" class="rounded-lg border border-gray-200 p-4">
        <template v-if="result.error">
          <div class="flex items-center gap-2 text-danger">
            <i class="pi pi-exclamation-circle" />
            <span class="font-medium">Lỗi: {{ result.error }}</span>
          </div>
        </template>
        <template v-else>
          <div class="mb-2 text-sm font-medium">Kết quả nhập:</div>
          <div class="flex gap-4 text-sm">
            <span class="text-success"
              ><i class="pi pi-check-circle" /> Đã tạo: {{ result.created }}</span
            >
            <span class="text-warning"
              ><i class="pi pi-exclamation-triangle" /> Bỏ qua: {{ result.skipped }}</span
            >
          </div>
          <ul v-if="result.errors?.length" class="mt-2 max-h-40 overflow-y-auto text-xs">
            <li v-for="(err, i) in result.errors" :key="i" class="text-danger">
              Dòng {{ err.row }}: {{ err.message }}
            </li>
          </ul>
        </template>
      </div>
    </div>

    <template #footer>
      <Button label="Hủy" severity="secondary" @click="$emit('update:visible', false)" />
      <Button label="Nhập" :disabled="!file || loading" :loading="loading" @click="importFile" />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import { patientsService } from '@/services/patients'
import type { AxiosError } from 'axios'

interface ImportResult {
  created?: number
  skipped?: number
  errors?: { row: number; message: string }[]
  error?: string
}

const props = defineProps<{ visible: boolean; companyId: string }>()
const emit = defineEmits<{
  'update:visible': [value: boolean]
  imported: []
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const file = ref<File | null>(null)
const isDragOver = ref(false)
const loading = ref(false)
const result = ref<ImportResult | null>(null)

function onInputChange(e: Event): void {
  const target = e.target as HTMLInputElement
  if (target.files?.[0]) {
    file.value = target.files[0]
    result.value = null
  }
}

function onDrop(e: DragEvent): void {
  isDragOver.value = false
  const dropped = e.dataTransfer?.files?.[0]
  if (dropped) {
    file.value = dropped
    result.value = null
  }
}

function clearFile(): void {
  file.value = null
  result.value = null
  if (fileInput.value) fileInput.value.value = ''
}

function formatSize(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(0)} KB`
}

async function importFile(): Promise<void> {
  if (!file.value) return
  loading.value = true
  result.value = null
  try {
    const formData = new FormData()
    formData.append('file', file.value)
    formData.append('company_id', props.companyId)
    const { data } = await patientsService.import(formData)
    result.value = data
    if (!data.error) emit('imported')
  } catch (err: unknown) {
    const axiosErr = err as AxiosError<{ detail?: string }>
    result.value = { error: axiosErr?.response?.data?.detail ?? 'Không thể nhập file' }
  } finally {
    loading.value = false
  }
}
</script>