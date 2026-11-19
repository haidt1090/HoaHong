<template>
  <div>
    <PageHeader
      title="Mapping XML"
      subtitle="Gắn thẻ hồ sơ quốc gia với khóa cột của khoa. Đổi mẫu khám không làm mất mapping nếu giữ nguyên khóa."
    />

    <SectionCard title="Cấu hình mapping" icon="pi pi-link">
      <p v-if="error && !dialogOpen && !uploadOpen" class="mb-3 text-sm text-red-600">{{ error }}</p>
      <div class="mb-4 flex flex-wrap items-end gap-3">
        <FormField label="Version" class="min-w-64 flex-1">
          <Select
            v-model="versionId"
            :options="versions"
            option-label="label"
            option-value="id"
            class="w-full"
            placeholder="Chưa có version"
            :disabled="!versions.length"
            @change="loadMappings"
          />
        </FormField>
        <Button
          v-if="selectedVersion && !selectedVersion.is_default"
          label="Đặt mặc định"
          icon="pi pi-check"
          severity="secondary"
          @click="makeDefault"
        />
        <span
          v-else-if="selectedVersion?.is_default"
          class="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700"
        >
          Mặc định
        </span>
        <Button label="Upload XML" icon="pi pi-upload" @click="openUpload" />
        <Button
          v-if="selectedVersion"
          label="Xóa version"
          icon="pi pi-trash"
          severity="danger"
          text
          @click="removeVersion"
        />
        <div class="ml-auto">
          <Button
            label="Thêm mapping"
            icon="pi pi-plus"
            :disabled="!versionId"
            @click="openCreate"
          />
        </div>
      </div>
      <p class="mb-4 text-xs text-text-muted">
        Đồng bộ dùng version mặc định. Upload file XML mẫu để lấy danh sách thẻ. Mapping trùng thẻ được sao chép từ version đang mặc định. File gốc không được lưu.
      </p>

      <DataTable :columns="columns" :data="rows" :loading="loading">
        <template #body-block="{ data }">
          {{ blockLabel(data.block) }}
        </template>
        <template #body-target="{ data }">
          <span class="font-mono text-xs">{{ data.xml_tag || data.ma_chi_so }}</span>
        </template>
        <template #body-source="{ data }">
          <div>
            <div>{{ data.department_name }} · {{ data.field_key }}</div>
            <div v-if="!data.field_present" class="text-xs text-amber-700">
              Khóa không còn trong mẫu hiện tại của khoa
            </div>
          </div>
        </template>
        <template #actions="{ data }">
          <Button icon="pi pi-pencil" text rounded @click="openEdit(data)" />
          <Button icon="pi pi-trash" text rounded severity="danger" @click="remove(data)" />
        </template>
        <template #empty>
          <EmptyState
            icon="pi pi-link"
            :title="versionId ? 'Chưa có mapping' : 'Chưa có version'"
            :description="
              versionId
                ? 'Chọn thẻ XML, khoa và khóa cột để đưa kết quả khám vào hồ sơ đồng bộ.'
                : 'Upload file XML mẫu để tạo version và lấy danh sách thẻ.'
            "
          />
        </template>
      </DataTable>
    </SectionCard>

    <Dialog
      v-model:visible="dialogOpen"
      modal
      :header="editingId ? 'Sửa mapping' : 'Thêm mapping'"
      class="w-[32rem]"
    >
      <div class="flex flex-col gap-4">
        <FormField label="Khối XML" required>
          <Select
            v-model="form.block"
            :options="blockOptions"
            option-label="label"
            option-value="value"
            class="w-full"
            @change="form.xml_tag = ''; labChoice = ''"
          />
        </FormField>

        <FormField v-if="form.block !== 'xml11'" label="Thẻ XML" required>
          <Select
            v-model="form.xml_tag"
            :options="tagsForBlock"
            option-label="label"
            option-value="tag"
            filter
            class="w-full"
            placeholder="Chọn thẻ"
          >
            <template #option="{ option }">
              <span>{{ option.label }}</span>
              <span class="ml-2 font-mono text-xs text-text-muted">{{ option.tag }}</span>
            </template>
          </Select>
        </FormField>

        <FormField v-else label="Chỉ số cận lâm sàng" required>
          <Select
            v-model="labChoice"
            :options="labOptions"
            option-label="label"
            option-value="code"
            filter
            class="w-full"
            placeholder="Chọn chỉ số trong file XML"
          />
        </FormField>

        <FormField label="Khoa" required>
          <Select
            v-model="form.department"
            :options="departments"
            option-label="name"
            option-value="id"
            filter
            class="w-full"
            placeholder="Chọn khoa"
          />
        </FormField>

        <FormField label="Khóa cột" required>
          <Select
            v-model="form.field_key"
            :options="fieldOptions"
            option-label="label"
            option-value="key"
            filter
            editable
            class="w-full"
            placeholder="chieu_cao"
          >
            <template #option="{ option }">
              <span class="font-mono text-xs">{{ option.key }}</span>
              <span class="ml-2">{{ option.label }}</span>
            </template>
          </Select>
          <p v-if="selectedField" class="mt-1 text-xs text-text-muted">
            Có trong mẫu: {{ selectedField.templates.join(', ') }}
          </p>
        </FormField>

        <FormField label="Khóa cũ">
          <InputText
            v-model="aliasText"
            class="w-full"
            placeholder="Các khóa trước đây, cách nhau bằng dấu phẩy"
          />
        </FormField>

        <p class="text-xs text-text-muted">
          Nếu gói khám không có khoa này, hệ thống tìm cùng khóa ở khoa khác của lượt khám.
          Khoa có trong gói nhưng ô trống thì thẻ XML để trống.
        </p>
        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
      </div>
      <template #footer>
        <Button label="Hủy" severity="secondary" text @click="dialogOpen = false" />
        <Button label="Lưu" icon="pi pi-save" :loading="saving" @click="save" />
      </template>
    </Dialog>

    <Dialog v-model:visible="uploadOpen" modal header="Upload XML" class="w-[28rem]">
      <div class="flex flex-col gap-4">
        <FormField label="Tên version">
          <InputText v-model="uploadName" class="w-full" placeholder="Để trống sẽ lấy tên file" />
        </FormField>
        <FormField label="File XML" required>
          <input
            ref="fileInput"
            type="file"
            accept=".xml,text/xml,application/xml"
            class="text-sm"
            @change="onFile"
          />
          <p v-if="uploadFile" class="text-xs text-text-muted">{{ uploadFile.name }}</p>
        </FormField>
        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
      </div>
      <template #footer>
        <Button label="Hủy" severity="secondary" text @click="uploadOpen = false" />
        <Button label="Tạo version" icon="pi pi-upload" :loading="uploading" @click="upload" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import DataTable from '@/components/common/DataTable.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import FormField from '@/components/common/FormField.vue'
import { useConfirm } from '@/composables/useConfirm'
import { api, extractError } from '@/services/api'
import type { ColumnDef } from '@/types'

interface MappingRow {
  id: string
  version: string
  block: string
  xml_tag: string
  department: string
  department_name: string
  field_key: string
  alias_keys: string[]
  ma_dich_vu: string
  ma_chi_so: string
  field_present: boolean
}

interface TagOption {
  block: string
  tag: string
  label: string
  ma_dich_vu: string
  ma_chi_so: string
}

interface VersionRow {
  id: string
  name: string
  label: string
  is_default: boolean
  field_count: number
}

interface FieldOption {
  key: string
  label: string
  templates: string[]
}

const blockOptions = [
  { value: 'xml7', label: 'XML7 — Khám lâm sàng' },
  { value: 'xml9', label: 'XML9 — Tiền sử' },
  { value: 'xml10', label: 'XML10 — Thể lực' },
  { value: 'xml11', label: 'XML11 — Cận lâm sàng' },
]

const columns: ColumnDef[] = [
  { field: 'block', header: 'Khối', width: '8rem' },
  { field: 'target', header: 'Thẻ XML' },
  { field: 'source', header: 'Khoa / khóa cột' },
]

const confirm = useConfirm()
const rows = ref<MappingRow[]>([])
const versions = ref<VersionRow[]>([])
const versionId = ref('')
const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const dialogOpen = ref(false)
const uploadOpen = ref(false)
const editingId = ref<string | null>(null)
const error = ref('')
const aliasText = ref('')
const uploadName = ref('')
const uploadFile = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const labChoice = ref('')
const departments = ref<{ id: string; name: string; code: string }[]>([])
const fieldsByDepartment = ref<Record<string, FieldOption[]>>({})
const tags = ref<TagOption[]>([])

const form = reactive({
  block: 'xml10',
  xml_tag: '',
  department: '' as string,
  field_key: '',
  ma_dich_vu: '',
  ma_chi_so: '',
})

const selectedVersion = computed(() => versions.value.find((item) => item.id === versionId.value))
const tagsForBlock = computed(() => tags.value.filter((tag) => tag.block === form.block && tag.tag))
const labOptions = computed(() =>
  tags.value
    .filter((tag) => tag.block === 'xml11')
    .map((tag) => ({
      code: `${tag.ma_dich_vu}|${tag.ma_chi_so}`,
      label: tag.ma_dich_vu
        ? `${tag.label} (${tag.ma_dich_vu} / ${tag.ma_chi_so})`
        : `${tag.label} (${tag.ma_chi_so})`,
      ma_dich_vu: tag.ma_dich_vu,
      ma_chi_so: tag.ma_chi_so,
    })),
)
const fieldOptions = computed(() => fieldsByDepartment.value[form.department] ?? [])
const selectedField = computed(() =>
  fieldOptions.value.find((field) => field.key === form.field_key),
)

function blockLabel(block: string): string {
  return blockOptions.find((item) => item.value === block)?.label ?? block
}

function versionLabel(row: { name: string; field_count: number; is_default: boolean }): string {
  const mark = row.is_default ? ' · mặc định' : ''
  return `${row.name} (${row.field_count} thẻ)${mark}`
}

async function loadVersions(preferId = '') {
  const response = await api.get<Omit<VersionRow, 'label'>[]>('/sync/mapping-versions/')
  versions.value = response.data.map((row) => ({ ...row, label: versionLabel(row) }))
  const stillThere = versions.value.some((row) => row.id === (preferId || versionId.value))
  if (!stillThere) {
    versionId.value =
      versions.value.find((row) => row.is_default)?.id || versions.value[0]?.id || ''
  } else if (preferId) {
    versionId.value = preferId
  }
}

async function loadMappings() {
  if (!versionId.value) {
    rows.value = []
    tags.value = []
    departments.value = []
    fieldsByDepartment.value = {}
    return
  }
  loading.value = true
  try {
    const [listRes, optionRes] = await Promise.all([
      api.get<MappingRow[]>('/sync/field-mappings/', { params: { version: versionId.value } }),
      api.get<{
        tags: TagOption[]
        departments: { id: string; name: string; code: string }[]
        fields: Record<string, FieldOption[]>
      }>('/sync/field-mappings/field-options/', { params: { version: versionId.value } }),
    ])
    rows.value = listRes.data
    tags.value = optionRes.data.tags
    departments.value = optionRes.data.departments
    fieldsByDepartment.value = optionRes.data.fields
  } catch (err) {
    error.value = extractError(err, 'Không tải được mapping.')
  } finally {
    loading.value = false
  }
}

async function load() {
  error.value = ''
  try {
    await loadVersions()
    await loadMappings()
  } catch (err) {
    error.value = extractError(err, 'Không tải được version mapping.')
  }
}

function openCreate() {
  editingId.value = null
  form.block = 'xml10'
  form.xml_tag = ''
  form.department = ''
  form.field_key = ''
  form.ma_dich_vu = ''
  form.ma_chi_so = ''
  labChoice.value = ''
  aliasText.value = ''
  error.value = ''
  dialogOpen.value = true
}

function openEdit(row: MappingRow) {
  editingId.value = row.id
  form.block = row.block
  form.xml_tag = row.xml_tag
  form.department = row.department
  form.field_key = row.field_key
  form.ma_dich_vu = row.ma_dich_vu
  form.ma_chi_so = row.ma_chi_so
  labChoice.value = row.ma_chi_so ? `${row.ma_dich_vu}|${row.ma_chi_so}` : ''
  aliasText.value = (row.alias_keys ?? []).join(', ')
  error.value = ''
  dialogOpen.value = true
}

function payload() {
  const lab = labOptions.value.find((item) => item.code === labChoice.value)
  return {
    version: versionId.value,
    block: form.block,
    xml_tag: form.block === 'xml11' ? '' : form.xml_tag,
    department: form.department,
    field_key: String(form.field_key || '').trim(),
    alias_keys: aliasText.value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean),
    ma_dich_vu: form.block === 'xml11' ? lab?.ma_dich_vu || '' : '',
    ma_chi_so: form.block === 'xml11' ? lab?.ma_chi_so || '' : '',
  }
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    if (editingId.value) {
      await api.put(`/sync/field-mappings/${editingId.value}/`, payload())
    } else {
      await api.post('/sync/field-mappings/', payload())
    }
    dialogOpen.value = false
    await loadMappings()
  } catch (err) {
    error.value = extractError(err, 'Không lưu được mapping.')
  } finally {
    saving.value = false
  }
}

async function remove(row: MappingRow) {
  const ok = await confirm.require(
    'Xóa mapping',
    `Xóa mapping ${row.xml_tag || row.ma_chi_so}?`,
    true,
  )
  if (!ok) return
  await api.delete(`/sync/field-mappings/${row.id}/`)
  await loadMappings()
}

function openUpload() {
  uploadName.value = ''
  uploadFile.value = null
  error.value = ''
  if (fileInput.value) fileInput.value.value = ''
  uploadOpen.value = true
}

function onFile(event: Event) {
  const input = event.target as HTMLInputElement
  uploadFile.value = input.files?.[0] ?? null
}

async function upload() {
  if (!uploadFile.value) {
    error.value = 'Chọn file XML.'
    return
  }
  uploading.value = true
  error.value = ''
  try {
    const body = new FormData()
    body.append('file', uploadFile.value)
    if (uploadName.value.trim()) body.append('name', uploadName.value.trim())
    const response = await api.post<VersionRow>('/sync/mapping-versions/', body, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    uploadOpen.value = false
    await loadVersions(response.data.id)
    await loadMappings()
  } catch (err) {
    error.value = extractError(err, 'Không đọc được file XML.')
  } finally {
    uploading.value = false
  }
}

async function makeDefault() {
  if (!versionId.value) return
  try {
    await api.post(`/sync/mapping-versions/${versionId.value}/set-default/`)
    await loadVersions(versionId.value)
  } catch (err) {
    error.value = extractError(err, 'Không đặt được version mặc định.')
  }
}

async function removeVersion() {
  if (!selectedVersion.value) return
  const ok = await confirm.require(
    'Xóa version',
    `Xóa version ${selectedVersion.value.name} và toàn bộ mapping của version này?`,
    true,
  )
  if (!ok) return
  await api.delete(`/sync/mapping-versions/${selectedVersion.value.id}/`)
  versionId.value = ''
  await load()
}

onMounted(load)
</script>
