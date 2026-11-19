<template>
  <Tag :value="config.label" :severity="config.severity" :class="{ 'text-xs': size === 'sm' }" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Tag from 'primevue/tag'

const props = withDefaults(
  defineProps<{
    status: string
    size?: 'sm' | 'md'
  }>(),
  { size: 'md' },
)

type TagSeverity = 'success' | 'info' | 'warn' | 'danger' | 'secondary'

const STATUS_MAP: Record<string, { label: string; severity: TagSeverity }> = {
  // Examination statuses
  draft: { label: 'Nháp', severity: 'warn' },
  completed: { label: 'Hoàn thành', severity: 'info' },
  confirmed: { label: 'Xác nhận', severity: 'success' },
  // Active flags
  active: { label: 'Hoạt động', severity: 'success' },
  inactive: { label: 'Ngừng', severity: 'danger' },
  // Pricing modes
  per_field: { label: 'Theo từng chỉ số', severity: 'info' },
  package_total: { label: 'Trọn gói', severity: 'secondary' },
  // Report statuses
  processing: { label: 'Đang xử lý', severity: 'warn' },
  done: { label: 'Hoàn thành', severity: 'success' },
  failed: { label: 'Lỗi', severity: 'danger' },
  // Sync job statuses
  pending: { label: 'Chờ xử lý', severity: 'info' },
}

const config = computed(
  () => STATUS_MAP[props.status] ?? { label: props.status, severity: 'secondary' as TagSeverity },
)
</script>
