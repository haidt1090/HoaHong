<template>
  <Select
    :key="String(modelValue ?? '')"
    :model-value="modelValue ?? null"
    :options="field.options ?? []"
    option-label="label"
    option-value="value"
    :disabled="disabled"
    :placeholder="'-- Chọn --'"
    show-clear
    fluid
    @update:model-value="$emit('update:modelValue', $event)"
  />
</template>

<script setup lang="ts">
import Select from 'primevue/select'
import type { FieldDefinition } from '@/types'

defineProps<{
  field: FieldDefinition
  modelValue: unknown
  disabled?: boolean
}>()

defineEmits<{
  'update:modelValue': [value: unknown]
}>()
</script>
