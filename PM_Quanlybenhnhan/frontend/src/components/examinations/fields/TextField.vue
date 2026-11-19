<template>
  <InputText
    :model-value="display"
    :disabled="disabled"
    :placeholder="field.placeholder"
    fluid
    @update:model-value="onType"
    @focus="onFocus"
    @blur="onBlur"
  />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import InputText from 'primevue/inputtext'
import type { FieldDefinition } from '@/types'
import { applyInputFormat } from '@/utils/inputFormat'

const props = defineProps<{
  field: FieldDefinition
  modelValue: unknown
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: unknown]
}>()

const focused = ref(false)
const draft = ref('')

function toText(value: unknown): string {
  if (value === null || value === undefined) return ''
  return String(value)
}

function formatted(value: unknown): string {
  return toText(applyInputFormat(props.field.input_format, value))
}

watch(
  () => props.modelValue,
  (value) => {
    if (!focused.value) draft.value = formatted(value)
  },
  { immediate: true },
)

const display = computed(() => (focused.value ? draft.value : formatted(props.modelValue)))

function onFocus(): void {
  focused.value = true
  draft.value = formatted(props.modelValue)
}

function onType(value: unknown): void {
  const text = value == null ? '' : String(value)
  draft.value = text
  if (!props.field.input_format) {
    emit('update:modelValue', text)
  }
}

function onBlur(): void {
  if (!focused.value) return
  focused.value = false
  const next = props.field.input_format
    ? applyInputFormat(props.field.input_format, draft.value)
    : draft.value
  emit('update:modelValue', next)
}
</script>
