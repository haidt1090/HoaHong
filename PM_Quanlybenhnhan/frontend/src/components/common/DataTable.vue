<template>
  <PrimeDataTable
    :value="data"
    :loading="loading"
    :paginator="paginator"
    :rows="rows"
    :total-records="totalRecords"
    :lazy="paginator"
    :rows-per-page-options="[10, 20, 50, 100]"
    data-key="id"
    removable-sort
    paginator-template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
    current-page-report-template="{first}-{last} / {totalRecords}"
    class="p-datatable-sm"
    :row-class="rowClass"
    :pt="{ table: { class: 'w-full' } }"
    @page="$emit('page', $event)"
    @sort="$emit('sort', $event)"
    @row-click="$emit('row-click', $event.data)"
  >
    <Column
      v-for="col in columns"
      :key="col.field"
      :field="col.field"
      :sortable="col.sortable"
      :style="col.width ? { width: col.width } : undefined"
    >
      <template #header>
        <slot :name="`header-${col.field}`" :column="col">
          {{ col.header }}
        </slot>
      </template>
      <template #body="slotProps">
        <slot :name="`body-${col.field}`" :data="slotProps.data" :value="slotProps.data[col.field]">
          {{ formatCell(slotProps.data[col.field]) }}
        </slot>
      </template>
    </Column>
    <Column v-if="$slots.actions" header="Thao tác" :style="{ width: '8rem' }">
      <template #body="slotProps">
        <slot name="actions" :data="slotProps.data" />
      </template>
    </Column>
    <template #empty>
      <slot name="empty">
        <div class="py-8 text-center text-text-muted">Không có dữ liệu</div>
      </slot>
    </template>
  </PrimeDataTable>
</template>

<script setup lang="ts">
import PrimeDataTable from 'primevue/datatable'
import Column from 'primevue/column'
import type { ColumnDef } from '@/types'

defineProps<{
  columns: ColumnDef[]
  data: unknown[]
  loading?: boolean
  paginator?: boolean
  totalRecords?: number
  rows?: number
  rowClass?: (data: unknown) => string | undefined
}>()

defineEmits<{
  page: [event: unknown]
  sort: [event: unknown]
  'row-click': [row: unknown]
}>()

function formatCell(value: unknown): string {
  if (value === null || value === undefined || value === '') return '--'
  return String(value)
}
</script>
