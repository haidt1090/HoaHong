<template>
  <div>
    <div v-if="loading" class="py-4 text-center text-sm text-text-muted">Đang tải chỉ số...</div>
    <EmptyState
      v-else-if="rows.length === 0"
      icon="pi pi-list"
      title="Không có chỉ số"
      description="Chọn gói khám để tải danh sách chỉ số."
    />
    <PrimeDataTable
      v-else
      :value="rows"
      size="small"
      scrollable
      scroll-height="320px"
      data-key="key"
    >
      <Column field="department_name" header="Khoa" />
      <Column field="label" header="Chỉ số" />
      <Column field="unit" header="Đơn vị">
        <template #body="{ data }">{{ data.unit || '--' }}</template>
      </Column>
      <Column header="Giá (VNĐ)" :style="{ width: '10rem' }">
        <template #body="{ data }">
          <InputNumber
            v-model="data.price"
            :min="0"
            mode="decimal"
            :use-grouping="true"
            input-class="w-28"
            @update:model-value="emitTotal"
          />
        </template>
      </Column>
      <template #footer>
        <div class="flex justify-between px-2 text-sm font-semibold">
          <span>Tổng cộng</span>
          <span class="text-warning">{{ formatCurrency(total) }}</span>
        </div>
      </template>
    </PrimeDataTable>
    <p class="mt-2 text-xs text-text-muted">
      Lưu ý: lưu giá chi tiết theo từng chỉ số sẽ hoàn thiện ở Sprint 6a.
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import PrimeDataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputNumber from 'primevue/inputnumber'
import EmptyState from '@/components/common/EmptyState.vue'
import { formatCurrency } from '@/utils/format'

export interface PricingFieldRow {
  department_name: string
  key: string
  label: string
  unit?: string
  price: number
}

const props = defineProps<{
  rows: PricingFieldRow[]
  loading?: boolean
}>()

const emit = defineEmits<{ total: [value: number] }>()

const total = computed(() => props.rows.reduce((sum, r) => sum + (Number(r.price) || 0), 0))

function emitTotal(): void {
  emit('total', total.value)
}

watch(total, (val) => emit('total', val), { immediate: true })
</script>
