<template>
  <MultiSelect
    :model-value="arrayValue"
    :options="field.options ?? []"
    option-label="label"
    option-value="value"
    :disabled="disabled"
    :placeholder="'-- Chọn --'"
    fluid
    @update:model-value="$emit('update:modelValue', $event)"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MultiSelect from 'primevue/multiselect'
import type { FieldDefinition } from '@/types'

const props = defineProps<{
  field: FieldDefinition
  modelValue: unknown
  disabled?: boolean
}>()

defineEmits<{
  'update:modelValue': [value: unknown]
}>()

const arrayValue = computed<string[]>(() => {
  if (Array.isArray(props.modelValue)) return props.modelValue as string[]
  return []
})
</script>
