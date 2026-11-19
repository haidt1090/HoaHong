<template>
  <Textarea
    :model-value="(modelValue ?? '') as string"
    :disabled="disabled"
    rows="3"
    auto-resize
    fluid
    @update:model-value="$emit('update:modelValue', $event)"
  />
</template>

<script setup lang="ts">
import Textarea from 'primevue/textarea'
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
