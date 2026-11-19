<template>
  <div class="mt-4 flex items-center justify-between gap-3 rounded-lg border border-gray-200 bg-white p-4">
    <div class="flex items-center gap-2">
      <span class="text-sm font-medium text-text-muted">Trạng thái:</span>
      <StatusBadge :status="status" />
    </div>
    <div class="flex gap-2">
      <Button
        v-if="canDelete"
        label="Xóa"
        icon="pi pi-trash"
        severity="danger"
        outlined
        @click="$emit('delete')"
      />
      <Button
        v-if="canComplete"
        label="Hoàn thành"
        icon="pi pi-check"
        @click="$emit('complete')"
      />
      <Button
        v-if="canConfirm"
        label="Xác nhận"
        icon="pi pi-check-circle"
        severity="success"
        @click="$emit('confirm')"
      />
      <Button
        v-if="canRevert"
        label="Về nháp"
        icon="pi pi-undo"
        severity="secondary"
        outlined
        @click="$emit('revert')"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Button from 'primevue/button'
import StatusBadge from '@/components/common/StatusBadge.vue'
import type { ExamStatus, Role } from '@/types'

const props = defineProps<{
  status: ExamStatus
  role: Role | null
  isOwner: boolean
}>()

defineEmits<{
  complete: []
  confirm: []
  delete: []
  revert: []
}>()

const canDelete = computed(() => {
  return props.status === 'draft' && (props.role === 'admin' || props.role === 'doctor' || (props.isOwner && (props.role === 'nurse' || props.role === 'labtech')))
})

const canComplete = computed(() => {
  return props.status === 'draft' && (props.role === 'admin' || props.role === 'doctor')
})

const canConfirm = computed(() => {
  return props.status === 'completed' && (props.role === 'admin' || props.role === 'doctor')
})

const canRevert = computed(() => {
  return props.status === 'confirmed' && props.role === 'admin'
})
</script>
