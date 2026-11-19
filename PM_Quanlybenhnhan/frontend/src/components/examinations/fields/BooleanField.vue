<template>
  <ToggleButton
    :model-value="boolValue"
    :disabled="disabled"
    on-label="Có"
    off-label="Không"
    on-icon="pi pi-check"
    off-icon="pi pi-times"
    @update:model-value="$emit('update:modelValue', $event)"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ToggleButton from 'primevue/togglebutton'
import type { FieldDefinition } from '@/types'

const props = defineProps<{
  field: FieldDefinition
  modelValue: unknown
  disabled?: boolean
}>()

defineEmits<{
  'update:modelValue': [value: unknown]
}>()

const boolValue = computed<boolean>(() => {
  return !!props.modelValue
})
</script>
