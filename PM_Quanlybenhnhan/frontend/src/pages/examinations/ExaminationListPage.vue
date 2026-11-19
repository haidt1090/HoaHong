<template>
  <div>
    <PageHeader title="Danh sách khám bệnh" subtitle="Quản lý các lượt khám sức khỏe">
      <template #actions>
        <Button
          label="Thêm khám"
          icon="pi pi-plus"
          @click="router.push({ name: 'exam-create' })"
        />
      </template>
    </PageHeader>

    <SectionCard>
      <div class="mb-4 flex flex-wrap items-center gap-3">
        <SearchBar v-model="store.filters.search" placeholder="Tìm bệnh nhân..." />
        <Select
          v-model="store.filters.company"
          :options="companyOptions"
          option-label="label"
          option-value="value"
          placeholder="Công ty"
          show-clear
          class="w-full sm:w-48"
        />
        <Select
          v-model="store.filters.status"
          :options="statusOptions"
          option-label="label"
          option-value="value"
          placeholder="Trạng thái"
          show-clear
          class="w-full sm:w-48"
        />
        <Select
          v-model="store.filters.exam_type"
          :options="examTypeOptions"
          option-label="label"
          option-value="value"
          placeholder="Loại khám"
          show-clear
          class="w-full sm:w-48"
        />
        <DatePicker
          v-model="dateFrom"
          placeholder="Từ ngày"
          date-format="dd/mm/yy"
          show-icon
          class="w-full sm:w-44"
        />
        <DatePicker
          v-model="dateTo"
          placeholder="Đến ngày"
          date-format="dd/mm/yy"
          show-icon
          class="w-full sm:w-44"
        />
      </div>

      <DataTable
        :columns="columns"
        :data="store.list"
        :loading="store.loading"
        paginator
        :rows="store.filters.page_size"
        :total-records="store.totalRecords"
        @page="onPage"
        @row-click="goToDetail"
      >
        <template #body-patient_name="{ data }">
          <span class="font-medium text-primary">{{ data.patient_name }}</span>
          <span v-if="data.employee_code" class="ml-1 text-xs text-text-muted">{{ data.employee_code }}</span>
        </template>
        <template #body-exam_type="{ value }">
          {{ examTypeLabel(value) }}
        </template>
        <template #body-status="{ value }">
          <StatusBadge :status="value" size="sm" />
        </template>
        <template #body-department_progress="{ data }">
          <DepartmentProgress
            v-if="data.departments_completed != null"
            :completed="data.departments_completed"
            :total="data.departments_total"
          />
          <span v-else>{{ data.department_progress }}</span>
        </template>
        <template #actions="{ data }">
          <ActionMenu :actions="rowActions(data)" @click.stop />
        </template>
        <template #empty>
          <EmptyState
            icon="pi pi-file-edit"
            title="Chưa có lượt khám"
            description="Tạo lượt khám đầu tiên để bắt đầu."
            action-label="Thêm khám"
            @action="router.push({ name: 'exam-create' })"
          />
        </template>
      </DataTable>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import SearchBar from '@/components/common/SearchBar.vue'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import ActionMenu from '@/components/common/ActionMenu.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import DepartmentProgress from '@/components/examinations/DepartmentProgress.vue'
import { useExamStore } from '@/stores/exams'
import { useAuth } from '@/composables/useAuth'
import { companiesService } from '@/services/companies'
import { examTypeLabel } from '@/utils/format'
import type { ColumnDef, ExamListItem, ActionDef, Company } from '@/types'

const router = useRouter()
const store = useExamStore()
const { isRole } = useAuth()

const dateFrom = ref<Date | null>(null)
const dateTo = ref<Date | null>(null)
const companies = ref<Company[]>([])

const companyOptions = computed(() =>
  companies.value.map((c) => ({ label: c.name, value: c.id })),
)

const columns: ColumnDef[] = [
  { field: 'patient_name', header: 'Bệnh nhân' },
  { field: 'company_name', header: 'Công ty' },
  { field: 'exam_type', header: 'Loại khám', width: '11rem' },
  { field: 'exam_date', header: 'Ngày khám', width: '9rem' },
  { field: 'doctor_name', header: 'Bác sĩ', width: '10rem' },
  { field: 'department_progress', header: 'Tiến độ', width: '10rem' },
  { field: 'status', header: 'Trạng thái', width: '9rem' },
]

const statusOptions = [
  { label: 'Nháp', value: 'draft' },
  { label: 'Hoàn thành', value: 'completed' },
  { label: 'Xác nhận', value: 'confirmed' },
]

const examTypeOptions = [
  { label: 'Khám định kỳ', value: 'periodic' },
  { label: 'Khám nghề nghiệp', value: 'occupational' },
  { label: 'Khám bố trí nghề nghiệp', value: 'job_placement' },
  { label: 'Khám lao động dưới 18', value: 'labor_under18' },
  { label: 'Khám lao động trên 18', value: 'labor_over18' },
]

function rowActions(exam: ExamListItem): ActionDef[] {
  const actions: ActionDef[] = [
    {
      label: 'Chi tiết',
      icon: 'pi pi-eye',
      handler: () => router.push({ name: 'exam-detail', params: { id: exam.id } }),
    },
  ]
  if (isRole('admin', 'doctor', 'nurse', 'labtech') && exam.status === 'draft') {
    actions.push({
      label: 'Sửa',
      icon: 'pi pi-pencil',
      handler: () => router.push({ name: 'exam-edit', params: { id: exam.id } }),
    })
  }
  return actions
}

function goToDetail(row: unknown) {
  const exam = row as ExamListItem
  router.push({ name: 'exam-detail', params: { id: exam.id } })
}

function onPage(event: unknown) {
  const e = event as { page: number; rows: number }
  store.filters.page = e.page + 1
  store.filters.page_size = e.rows
  store.fetchList()
}

let searchDebounce: ReturnType<typeof setTimeout> | undefined

watch(dateFrom, (val) => {
  store.filters.date_from = val ? val.toISOString().slice(0, 10) : null
})
watch(dateTo, (val) => {
  store.filters.date_to = val ? val.toISOString().slice(0, 10) : null
})

watch(
  () => [store.filters.search, store.filters.company, store.filters.status, store.filters.exam_type, store.filters.date_from, store.filters.date_to],
  () => {
    if (searchDebounce) clearTimeout(searchDebounce)
    searchDebounce = setTimeout(() => {
      store.filters.page = 1
      store.fetchList()
    }, 100)
  },
)

onMounted(async () => {
  store.fetchList()
  try {
    const { data } = await companiesService.list({ page_size: 200 })
    companies.value = (data as { results?: Company[] }).results || (data as unknown as Company[])
  } catch {
    // ignore
  }
})
</script>
