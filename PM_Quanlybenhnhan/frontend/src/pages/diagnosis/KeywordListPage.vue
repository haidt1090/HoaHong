<template>
  <div>
    <PageHeader title="Quản lý từ khóa chẩn đoán">
      <template #actions>
        <Button label="Thêm từ khóa" icon="pi pi-plus" class="mr-2" @click="openCreate" />
        <Button label="Import Excel" icon="pi pi-upload" severity="secondary" outlined @click="onImportClick" />
      </template>
    </PageHeader>

    <SectionCard>
      <div class="mb-4 flex flex-wrap gap-3">
        <div class="flex-1 min-w-[200px]">
          <SearchBar v-model="store.keywordFilters.search" placeholder="Tìm từ khóa..." />
        </div>
        <Select
          v-model="store.keywordFilters.classification"
          :options="classificationOptions"
          option-label="label"
          option-value="value"
          placeholder="-- Phân loại --"
          show-clear
          class="w-48"
          @change="onFilterChange"
        />
      </div>

      <DataTable
        :columns="columns"
        :data="store.keywords"
        :loading="store.keywordsLoading"
        paginator
        :rows="store.keywordFilters.page_size"
        :total-records="store.keywordTotal"
        @page="onPage"
      >
        <template #body-disease_name="{ data }">
          <span class="font-medium text-text-body">{{ data.disease_name }}</span>
        </template>
        <template #body-classification="{ value }">
          <Tag
            v-if="value === DiagnosisClassification.UNFIT"
            value="Loại 5"
            severity="danger"
          />
          <Tag
            v-else-if="value === DiagnosisClassification.POOR"
            value="Loại 4"
            severity="danger"
          />
          <Tag
            v-else-if="value === DiagnosisClassification.DISEASE"
            value="Loại 3"
            severity="info"
          />
          <Tag
            v-else-if="value === DiagnosisClassification.MILD"
            value="Loại 2"
            severity="success"
          />
          <Tag
            v-else-if="value === DiagnosisClassification.GOOD"
            value="Loại 1"
            severity="secondary"
          />
          <span v-else>--</span>
        </template>
        <template #body-is_active="{ value }">
          <StatusBadge :status="value ? 'active' : 'inactive'" size="sm" />
        </template>
        <template #actions="{ data }">
          <div class="flex gap-1">
            <Button icon="pi pi-pencil" size="small" text rounded severity="info" @click="openEdit(data)" />
            <Button icon="pi pi-trash" size="small" text rounded severity="danger" @click="onDelete(data)" />
          </div>
        </template>
        <template #empty>
          <EmptyState icon="pi pi-tags" title="Chưa có từ khóa" action-label="Thêm từ khóa" @action="openCreate" />
        </template>
      </DataTable>
    </SectionCard>

    <!-- Create/Edit Dialog -->
    <Dialog
      v-model:visible="dialogVisible"
      :header="editingKeyword ? 'Sửa từ khóa' : 'Thêm từ khóa'"
      :modal="true"
      :style="{ width: '560px' }"
    >
      <div class="flex flex-col gap-3">
        <div>
          <label class="mb-1 block text-sm font-medium">Từ khóa <span class="text-red-500">*</span></label>
          <InputText v-model="form.keyword" placeholder="VD: huyết áp cao" fluid />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium">Tên bệnh</label>
          <InputText v-model="form.disease_name" placeholder="VD: Tăng huyết áp" fluid />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium">Mẫu tư vấn</label>
          <Textarea v-model="form.conclusion_template" rows="3" placeholder="VD: Cần vận động nhẹ nhàng..." fluid />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium">Phân loại sức khỏe</label>
          <Select
            v-model="form.classification"
            :options="classificationOptions"
            option-label="label"
            option-value="value"
            placeholder="-- Chọn phân loại --"
            show-clear
            fluid
          />
        </div>
      </div>
      <template #footer>
        <Button label="Hủy" severity="secondary" outlined @click="dialogVisible = false" />
        <Button label="Lưu" :loading="saving" @click="onSave" />
      </template>
    </Dialog>

    <!-- Import Dialog -->
    <Dialog
      v-model:visible="importVisible"
      header="Import từ khóa từ Excel"
      :modal="true"
      :style="{ width: '480px' }"
    >
      <div class="flex flex-col gap-3">
        <p class="text-sm text-text-secondary">
          Upload file Benh-TuVan 001.xlsx để import từ khóa chẩn đoán.
        </p>
        <div>
          <label class="mb-1 block text-sm font-medium">Chế độ import</label>
          <Select
            v-model="importMode"
            :options="[
              { label: 'Thêm mới (giữ dữ liệu cũ)', value: 'append' },
              { label: 'Thay thế toàn bộ', value: 'replace' },
            ]"
            option-label="label"
            option-value="value"
            fluid
          />
        </div>
        <FileUpload
          ref="fileUpload"
          mode="basic"
          accept=".xlsx"
          :max-file-size="10000000"
          choose-label="Chọn file Excel"
          @select="onFileSelect"
        />
      </div>
      <template #footer>
        <Button label="Hủy" severity="secondary" outlined @click="importVisible = false" />
        <Button label="Import" :loading="importing" :disabled="!selectedFile" @click="onImport" />
      </template>
    </Dialog>

    <Message v-if="importResult" severity="success" :closable="true" class="mt-4" @close="importResult = null">
      Import thành công: {{ importResult.keywords_created }} từ khóa.
    </Message>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import FileUpload from 'primevue/fileupload'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import SearchBar from '@/components/common/SearchBar.vue'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useDiagnosisStore } from '@/stores/diagnosis'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { extractError } from '@/services/api'
import { DiagnosisClassification } from '@/types'
import type { DiagnosisKeyword, DiagnosisKeywordInput, ColumnDef } from '@/types'

const store = useDiagnosisStore()
const toast = useToast()
const confirm = useConfirm()

const dialogVisible = ref(false)
const editingKeyword = ref<DiagnosisKeyword | null>(null)
const saving = ref(false)

const importVisible = ref(false)
const importing = ref(false)
const selectedFile = ref<File | null>(null)
const importMode = ref<'append' | 'replace'>('append')
const importResult = ref<{ diseases_created: number; keywords_created: number } | null>(null)

const emptyForm = (): DiagnosisKeywordInput => ({
  keyword: '',
  disease_name: '',
  conclusion_template: '',
  classification: null,
})

const form = reactive<DiagnosisKeywordInput>(emptyForm())

const classificationOptions = [
  { label: 'Loại 1', value: 1 },
  { label: 'Loại 2', value: 2 },
  { label: 'Loại 3', value: 3 },
  { label: 'Loại 4', value: 4 },
  { label: 'Loại 5', value: 5 },
]

const columns: ColumnDef[] = [
  { field: 'keyword', header: 'Từ khóa', sortable: true },
  { field: 'disease_name', header: 'Tên bệnh', width: '14rem' },
  { field: 'conclusion_template', header: 'Tư vấn' },
  { field: 'classification', header: 'Phân loại', width: '8rem' },
  { field: 'is_active', header: 'TT', width: '4rem' },
]

function openCreate() {
  editingKeyword.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(kw: DiagnosisKeyword) {
  editingKeyword.value = kw
  Object.assign(form, {
    keyword: kw.keyword,
    disease_name: kw.disease_name,
    conclusion_template: kw.conclusion_template,
    classification: kw.classification,
  })
  dialogVisible.value = true
}

async function onSave() {
  if (!form.keyword) {
    toast.showError('Vui lòng nhập từ khóa')
    return
  }
  saving.value = true
  try {
    if (editingKeyword.value) {
      await store.updateKeyword(editingKeyword.value.id, { ...form })
      toast.showSuccess('Đã cập nhật từ khóa')
    } else {
      await store.createKeyword({ ...form })
      toast.showSuccess('Đã thêm từ khóa')
    }
    dialogVisible.value = false
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi khi lưu'))
  } finally {
    saving.value = false
  }
}

async function onDelete(kw: DiagnosisKeyword) {
  const ok = await confirm.require('Xóa từ khóa', `Xóa từ khóa "${kw.keyword}"?`, true)
  if (!ok) return
  try {
    await store.removeKeyword(kw.id)
    toast.showSuccess('Đã xóa')
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi khi xóa'))
  }
}

function onImportClick() {
  importResult.value = null
  importVisible.value = true
}

function onFileSelect(e: { files: File[] }) {
  selectedFile.value = e.files[0] ?? null
}

async function onImport() {
  if (!selectedFile.value) return
  importing.value = true
  try {
    importResult.value = await store.importKeywords(selectedFile.value, importMode.value)
    toast.showSuccess('Import thành công')
    importVisible.value = false
    selectedFile.value = null
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi khi import'))
  } finally {
    importing.value = false
  }
}

function onFilterChange() {
  store.keywordFilters.page = 1
  store.fetchKeywords()
}

function onPage(event: unknown) {
  const e = event as { first: number; rows: number }
  store.keywordFilters.page = Math.floor(e.first / e.rows) + 1
  store.fetchKeywords()
}

watch(
  () => store.keywordFilters.search,
  () => {
    store.keywordFilters.page = 1
    store.fetchKeywords()
  },
  { immediate: false },
)

onMounted(async () => {
  await store.fetchKeywords()
})
</script>
