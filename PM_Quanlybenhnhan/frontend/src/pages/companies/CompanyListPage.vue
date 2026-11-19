<template>
  <div>
    <PageHeader title="Danh sách công ty">
      <template #actions>
        <Button
          v-if="isRole('admin')"
          label="Thêm công ty"
          icon="pi pi-plus"
          @click="router.push({ name: 'company-create' })"
        />
      </template>
    </PageHeader>

    <SectionCard>
      <div class="mb-4">
        <SearchBar v-model="store.filters.search" placeholder="Tìm công ty..." />
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
        <template #body-name="{ data }">
          <span class="font-medium text-primary">{{ data.name }}</span>
        </template>
        <template #body-is_active="{ value }">
          <StatusBadge :status="value ? 'active' : 'inactive'" size="sm" />
        </template>
        <template #actions="{ data }">
          <ActionMenu :actions="rowActions(data)" @click.stop />
        </template>
        <template #empty>
          <EmptyState
            icon="pi pi-building"
            title="Chưa có công ty"
            :action-label="isRole('admin') ? 'Thêm công ty' : undefined"
            @action="router.push({ name: 'company-create' })"
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
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import SearchBar from '@/components/common/SearchBar.vue'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import ActionMenu from '@/components/common/ActionMenu.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useCompanyStore } from '@/stores/companies'
import { useAuth } from '@/composables/useAuth'
import type { ColumnDef, Company, ActionDef } from '@/types'

const router = useRouter()
const store = useCompanyStore()
const { isRole } = useAuth()

const columns: ColumnDef[] = [
  { field: 'name', header: 'Tên công ty', sortable: true },
  { field: 'tax_code', header: 'Mã số thuế', width: '10rem' },
  { field: 'contact_person', header: 'Người liên hệ' },
  { field: 'contact_phone', header: 'Điện thoại', width: '10rem' },
  { field: 'patient_count', header: 'Số NV', width: '7rem' },
  { field: 'is_active', header: 'Trạng thái', width: '9rem' },
]

function rowActions(company: Company): ActionDef[] {
  const actions: ActionDef[] = [
    {
      label: 'Chi tiết',
      icon: 'pi pi-eye',
      handler: () => router.push({ name: 'company-detail', params: { id: company.id } }),
    },
  ]
  if (isRole('admin')) {
    actions.push(
      {
        label: 'Gói khám',
        icon: 'pi pi-box',
        handler: () => router.push({ name: 'company-packages', params: { id: company.id } }),
      },
      {
        label: 'Sửa',
        icon: 'pi pi-pencil',
        handler: () => router.push({ name: 'company-edit', params: { id: company.id } }),
      },
    )
  }
  return actions
}

function goToDetail(row: unknown): void {
  const company = row as Company
  router.push({ name: 'company-detail', params: { id: company.id } })
}

function onPage(event: unknown): void {
  const e = event as { page: number; rows: number }
  store.filters.page = e.page + 1
  store.filters.page_size = e.rows
  store.fetchList()
}

let searchDebounce: ReturnType<typeof setTimeout> | undefined
watch(
  () => store.filters.search,
  () => {
    if (searchDebounce) clearTimeout(searchDebounce)
    searchDebounce = setTimeout(() => {
      store.filters.page = 1
      store.fetchList()
    }, 100)
  },
)

onMounted(() => store.fetchList())
</script>
