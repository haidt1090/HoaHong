<template>
  <div>
    <PageHeader
      title="Chữ ký hồ sơ (ảnh)"
      subtitle="CKS_NGUOI_KET_LUAN để trống khi đồng bộ. Bác sĩ ký phiếu sau trên cổng CSDLKSK."
    />

    <div class="mb-6 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
      <p class="font-semibold">Lưu ý CSDLKSK</p>
      <p class="mt-1">
        <code>CKS_NGUOI_KET_LUAN</code> để trống. Bác sĩ bấm Ký phiếu khám trên cổng sau khi dữ liệu đã lên.
        USB token trên máy này là chữ ký của cơ sở khám, ghi vào <code>CKS_BENH_VIEN</code>.
        Ảnh trên trang này không thay chữ ký USB.
      </p>
    </div>

    <SectionCard title="Chữ ký bệnh viện (ảnh)" icon="pi pi-building" class="mb-6">
      <p class="mb-4 text-sm text-text-muted">
        Không bắt buộc. Nếu đã cấu hình, giá trị được ghi vào CKS_BENH_VIEN khi đồng bộ.
        Cổng quốc gia có thể vẫn báo chữ ký không hợp lệ nếu đây chỉ là ảnh PNG.
      </p>
      <div class="flex flex-wrap items-center gap-3">
        <Tag v-if="facilityKind === 'image'" value="Ảnh PNG" severity="success" />
        <Tag v-else-if="facilityKind === 'base64'" value="Base64" severity="info" />
        <Tag v-else value="Chưa có" severity="secondary" />
        <Button label="Cấu hình" icon="pi pi-pencil" size="small" outlined @click="openFacility" />
        <Button
          label="Xóa"
          icon="pi pi-trash"
          size="small"
          severity="danger"
          text
          :disabled="!facilityKind"
          @click="clearFacility"
        />
      </div>
    </SectionCard>

    <SectionCard title="Chữ ký bác sĩ kết luận (ảnh)">
      <DataTable :columns="columns" :data="doctors" :loading="loading">
        <template #body-full_name="{ data }">
          <span class="font-medium text-text-body">{{ data.full_name }}</span>
        </template>
        <template #body-signature_kind="{ data }">
          <Tag v-if="data.signature_kind === 'image'" value="Ảnh PNG" severity="success" />
          <Tag v-else-if="data.signature_kind === 'base64'" value="Base64" severity="info" />
          <Tag v-else value="Chưa có" severity="secondary" />
        </template>
        <template #actions="{ data }">
          <div class="flex gap-1">
            <Button icon="pi pi-pencil" size="small" text rounded @click="openEdit(data)" />
            <Button
              icon="pi pi-trash"
              size="small"
              text
              rounded
              severity="danger"
              :disabled="!data.signature_kind"
              @click="onClear(data)"
            />
          </div>
        </template>
        <template #empty>
          <EmptyState icon="pi pi-user" title="Chưa có bác sĩ" />
        </template>
      </DataTable>
    </SectionCard>

    <Dialog
      v-model:visible="dialogOpen"
      modal
      :header="editingFacility ? 'Chữ ký bệnh viện' : 'Chữ ký bác sĩ'"
      :style="{ width: '36rem' }"
      @hide="closeDialog"
    >
      <p v-if="editing" class="mb-4 text-sm text-text-muted">
        {{ editing.full_name }} · {{ editing.email }}
      </p>

      <div class="mb-4 flex gap-2">
        <Button
          label="Ảnh PNG"
          size="small"
          :outlined="mode !== 'image'"
          @click="mode = 'image'"
        />
        <Button
          label="Chuỗi base64"
          size="small"
          :outlined="mode !== 'base64'"
          @click="mode = 'base64'"
        />
      </div>

      <div v-if="mode === 'image'" class="flex flex-col gap-3">
        <input type="file" accept="image/png,.png" class="text-sm" @change="onFile" />
        <img
          v-if="previewUrl"
          :src="previewUrl"
          alt="Xem trước chữ ký"
          class="max-h-40 max-w-full rounded border border-gray-200 bg-white p-2"
        />
        <p v-else-if="(editingFacility ? facilityKind : editing?.signature_kind) === 'image'" class="text-sm text-text-muted">
          Đã lưu ảnh PNG. Chọn file mới để thay.
        </p>
      </div>

      <FormField v-else label="Base64">
        <Textarea
          v-model="base64Text"
          rows="6"
          class="w-full font-mono text-xs"
          placeholder="Dán chuỗi base64 (có thể kèm tiền tố data:image/png;base64,)"
        />
      </FormField>

      <p v-if="error" class="mt-3 text-sm text-red-600">{{ error }}</p>

      <template #footer>
        <Button label="Hủy" severity="secondary" text @click="dialogOpen = false" />
        <Button label="Lưu" icon="pi pi-save" :loading="saving" @click="save" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import { useToast } from '@/composables/useToast'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import DataTable from '@/components/common/DataTable.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import FormField from '@/components/common/FormField.vue'
import { api } from '@/services/api'
import type { DoctorSignatureKind, DoctorSignatureRow } from '@/types'

const toast = useToast()
const doctors = ref<DoctorSignatureRow[]>([])
const facilityKind = ref<DoctorSignatureKind>('')
const editingFacility = ref(false)
const loading = ref(false)
const saving = ref(false)
const dialogOpen = ref(false)
const editing = ref<DoctorSignatureRow | null>(null)
const mode = ref<'image' | 'base64'>('image')
const file = ref<File | null>(null)
const previewUrl = ref('')
const base64Text = ref('')
const error = ref('')

const columns = [
  { field: 'full_name', header: 'Bác sĩ', sortable: true },
  { field: 'email', header: 'Email', sortable: true },
  { field: 'signature_kind', header: 'Chữ ký' },
]

async function load(): Promise<void> {
  loading.value = true
  try {
    const [doctorRes, facilityRes] = await Promise.all([
      api.get<DoctorSignatureRow[]>('/auth/doctor-signatures/'),
      api.get<{ signature_kind: DoctorSignatureKind }>('/sync/facility-signature/'),
    ])
    doctors.value = doctorRes.data
    facilityKind.value = facilityRes.data.signature_kind
  } catch {
    toast.showError('Không tải được danh sách bác sĩ')
  } finally {
    loading.value = false
  }
}

function revokePreview(): void {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

async function openFacility(): Promise<void> {
  revokePreview()
  editingFacility.value = true
  editing.value = null
  mode.value = facilityKind.value === 'base64' ? 'base64' : 'image'
  file.value = null
  base64Text.value = ''
  error.value = ''
  dialogOpen.value = true
  if (facilityKind.value === 'image') {
    try {
      const { data } = await api.get('/sync/facility-signature/image/', { responseType: 'blob' })
      previewUrl.value = URL.createObjectURL(data)
    } catch {
      previewUrl.value = ''
    }
  }
}

async function openEdit(row: DoctorSignatureRow): Promise<void> {
  revokePreview()
  editingFacility.value = false
  editing.value = row
  mode.value = row.signature_kind === 'base64' ? 'base64' : 'image'
  file.value = null
  base64Text.value = ''
  error.value = ''
  dialogOpen.value = true
  if (row.signature_kind === 'image') {
    try {
      const { data } = await api.get(`/auth/doctor-signatures/${row.id}/image/`, {
        responseType: 'blob',
      })
      previewUrl.value = URL.createObjectURL(data)
    } catch {
      previewUrl.value = ''
    }
  }
}

function closeDialog(): void {
  revokePreview()
  file.value = null
  error.value = ''
}

function onFile(event: Event): void {
  const input = event.target as HTMLInputElement
  const picked = input.files?.[0] ?? null
  file.value = picked
  revokePreview()
  if (picked) {
    previewUrl.value = URL.createObjectURL(picked)
  }
}

function signatureUrl(): string {
  return editingFacility.value
    ? '/sync/facility-signature/'
    : `/auth/doctor-signatures/${editing.value?.id}/`
}

async function save(): Promise<void> {
  if (!editingFacility.value && !editing.value) return
  error.value = ''
  saving.value = true
  try {
    if (mode.value === 'image') {
      if (!file.value) {
        error.value = 'Chọn file PNG.'
        return
      }
      if (!file.value.name.toLowerCase().endsWith('.png') && file.value.type !== 'image/png') {
        error.value = 'Chỉ nhận file ảnh PNG.'
        return
      }
      const body = new FormData()
      body.append('signature_image', file.value)
      await api.put(signatureUrl(), body, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    } else {
      if (!base64Text.value.trim()) {
        error.value = 'Dán chuỗi base64.'
        return
      }
      await api.put(signatureUrl(), { signature_base64: base64Text.value })
    }
    toast.showSuccess('Đã lưu chữ ký')
    dialogOpen.value = false
    await load()
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
    error.value = detail || 'Không lưu được chữ ký.'
  } finally {
    saving.value = false
  }
}

async function clearFacility(): Promise<void> {
  if (!window.confirm('Xóa chữ ký bệnh viện?')) return
  try {
    await api.delete('/sync/facility-signature/')
    toast.showSuccess('Đã xóa chữ ký bệnh viện')
    await load()
  } catch {
    toast.showError('Không xóa được chữ ký bệnh viện')
  }
}

async function onClear(row: DoctorSignatureRow): Promise<void> {
  if (!window.confirm(`Xóa chữ ký của ${row.full_name}?`)) return
  try {
    await api.delete(`/auth/doctor-signatures/${row.id}/`)
    toast.showSuccess('Đã xóa chữ ký')
    await load()
  } catch {
    toast.showError('Không xóa được chữ ký')
  }
}

onBeforeUnmount(revokePreview)
load()
</script>
