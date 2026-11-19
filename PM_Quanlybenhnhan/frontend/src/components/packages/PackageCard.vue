<template>
  <div class="rounded-lg border border-gray-200 bg-white p-5">
    <div class="mb-4 flex items-start justify-between gap-2">
      <h3 class="m-0 text-base font-semibold text-text-body">{{ pkg.package_detail?.name }}</h3>
      <StatusBadge :status="pkg.pricing_mode" size="sm" />
    </div>

    <dl class="m-0 flex flex-col gap-2">
      <div class="flex justify-between text-sm">
        <dt class="text-text-muted">Loại khám</dt>
        <dd class="m-0 font-medium">{{ examTypeLabel(pkg.package_detail?.exam_type) }}</dd>
      </div>
      <div class="flex justify-between text-sm">
        <dt class="text-text-muted">Số nhân viên</dt>
        <dd class="m-0 font-medium">{{ pkg.total_employees }}</dd>
      </div>
      <div class="flex justify-between text-sm">
        <dt class="text-text-muted">Tổng chi phí</dt>
        <dd class="m-0 font-semibold text-warning">{{ formatCurrency(pkg.total_cost) }}</dd>
      </div>
      <div class="flex justify-between text-sm">
        <dt class="text-text-muted">Trạng thái</dt>
        <dd class="m-0">
          <StatusBadge :status="pkg.is_active ? 'active' : 'inactive'" size="sm" />
        </dd>
      </div>
    </dl>

    <div class="mt-4 flex gap-2 border-t border-gray-100 pt-3">
      <Button label="Sửa" icon="pi pi-pencil" size="small" outlined @click="$emit('edit', pkg)" />
      <Button
        label="Ngừng"
        icon="pi pi-ban"
        size="small"
        severity="danger"
        outlined
        @click="$emit('deactivate', pkg)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import Button from 'primevue/button'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { examTypeLabel, formatCurrency } from '@/utils/format'
import type { CompanyExamPackage } from '@/types'

defineProps<{ pkg: CompanyExamPackage }>()

defineEmits<{
  edit: [pkg: CompanyExamPackage]
  deactivate: [pkg: CompanyExamPackage]
}>()
</script>
