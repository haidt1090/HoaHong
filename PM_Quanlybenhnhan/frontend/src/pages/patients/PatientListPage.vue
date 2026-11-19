<template>
  <div>
    <PageHeader title="Danh sách bệnh nhân">
      <template #actions>
        <Button
          label="Thêm bệnh nhân"
          icon="pi pi-user-plus"
          @click="router.push({ name: 'patient-create' })"
        />
      </template>
    </PageHeader>

    <SectionCard>
      <div class="mb-4 flex flex-wrap items-center gap-3">
        <SearchBar v-model="store.filters.search" placeholder="Tìm tên, mã NV, CCCD, SĐT..." />
        <Select
          v-model="store.filters.company"
          :options="companyOptions"
          option-label="name"
          option-value="id"
          placeholder="Tất cả công ty"
          show-clear
          filter
          class="w-full sm:w-64"
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
        <template #body-full_name="{ data }">
          <span class="font-medium text-primary">{{ data.full_name }}</span>
        </template>
        <template #body-gender="{ value }">{{ genderLabel(value) }}</template>
        <template #body-company="{ data }">{{ data.company_detail?.name || 'Cá nhân' }}</template>
        <template #body-is_active="{ value }">
          <StatusBadge :status="value ? 'active' : 'inactive'" size="sm" />
        </template>
        <template #actions="{ data }">
          <ActionMenu :actions="rowActions(data)" @click.stop />
        </template>
        <template #empty>
          <EmptyState
            icon="pi pi-users"
            title="Chưa có bệnh nhân"
            description="Thêm bệnh nhân đầu tiên để bắt đầu."
            action-label="Thêm bệnh nhân"
            @action="router.push({ name: 'patient-create' })"
          />
        </template>
      </DataTable>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Select from 'primevue/select'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import SearchBar from '@/components/common/SearchBar.vue'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import ActionMenu from '@/components/common/ActionMenu.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { usePatientStore } from '@/stores/patients'
import { useCompanyStore } from '@/stores/companies'
import { useAuth } from '@/composables/useAuth'
import { genderLabel } from '@/utils/format'
import type { ColumnDef, Patient, Company, ActionDef } from '@/types'

const router = useRouter()
const store = usePatientStore()
const companyStore = useCompanyStore()
const { isRole } = useAuth()

const companyOptions = companyStore.list as unknown as Company[]

const columns: ColumnDef[] = [
  { field: 'employee_code', header: 'Mã NV', width: '8rem' },
  { field: 'full_name', header: 'Họ tên', sortable: true },
  { field: 'dob', header: 'Ngày sinh', width: '10rem' },
  { field: 'gender', header: 'Giới tính', width: '8rem' },
  { field: 'company', header: 'Công ty' },
  { field: 'department', header: 'Phòng ban' },
  { field: 'is_active', header: 'Trạng thái', width: '9rem' },
]

function rowActions(patient: Patient): ActionDef[] {
  const actions: ActionDef[] = [
    {
      label: 'Chi tiết',
      icon: 'pi pi-eye',
      handler: () => router.push({ name: 'patient-detail', params: { id: patient.id } }),
    },
  ]
  if (isRole('admin', 'doctor', 'nurse')) {
    actions.push({
      label: 'Sửa',
      icon: 'pi pi-pencil',
      handler: () => router.push({ name: 'patient-edit', params: { id: patient.id } }),
    })
  }
  return actions
}

function goToDetail(row: unknown): void {
  const patient = row as Patient
  router.push({ name: 'patient-detail', params: { id: patient.id } })
}

function onPage(event: unknown): void {
  const e = event as { page: number; rows: number }
  store.filters.page = e.page + 1
  store.filters.page_size = e.rows
  store.fetchList()
}

let searchDebounce: ReturnType<typeof setTimeout> | undefined
watch(
  () => [store.filters.search, store.filters.company],
  () => {
    if (searchDebounce) clearTimeout(searchDebounce)
    searchDebounce = setTimeout(() => {
      store.filters.page = 1
      store.fetchList()
    }, 100)
  },
)

onMounted(async () => {
  await store.fetchList()
  if (isRole('admin', 'doctor')) {
    companyStore.filters.page_size = 200
    await companyStore.fetchList()
  }
})
</script>
