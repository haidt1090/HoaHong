<template>
  <DatePicker
    :model-value="dateValue"
    :disabled="disabled"
    date-format="dd/mm/yy"
    show-icon
    fluid
    @update:model-value="$emit('update:modelValue', $event ? formatDate($event) : null)"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DatePicker from 'primevue/datepicker'
import type { FieldDefinition } from '@/types'

const props = defineProps<{
  field: FieldDefinition
  modelValue: unknown
  disabled?: boolean
}>()

defineEmits<{
  'update:modelValue': [value: unknown]
}>()

const dateValue = computed<Date | null>(() => {
  if (!props.modelValue || typeof props.modelValue !== 'string') return null
  const d = new Date(props.modelValue)
  return isNaN(d.getTime()) ? null : d
})

function formatDate(d: unknown): string | null {
  if (d instanceof Date && !isNaN(d.getTime())) {
    return d.toISOString().slice(0, 10)
  }
  return null
}
</script>
