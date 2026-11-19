<template>
  <div class="flex items-center gap-2" @focusin="onFocus" @focusout="onBlur">
    <InputText
      :model-value="display"
      :disabled="disabled"
      inputmode="decimal"
      fluid
      class="flex-1"
      :class="rangeClass"
      @update:model-value="onType"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import InputText from 'primevue/inputtext'
import type { FieldDefinition } from '@/types'
import { baseNormalRange } from '@/utils/field'

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
  if (value === null || value === undefined || value === '') return ''
  const n = Number(value)
  return Number.isFinite(n) ? String(n) : ''
}

function parseNumber(text: string): number | null {
  const t = text.trim().replace(',', '.')
  if (t === '' || t === '-' || t === '.' || t === '-.') return null
  const n = Number(t)
  return Number.isFinite(n) ? n : null
}

watch(
  () => props.modelValue,
  (value) => {
    if (!focused.value) draft.value = toText(value)
  },
  { immediate: true },
)

const display = computed(() => (focused.value ? draft.value : toText(props.modelValue)))

const numericValue = computed<number | null>(() => parseNumber(toText(props.modelValue)))

function onFocus(): void {
  focused.value = true
  draft.value = toText(props.modelValue)
}

function onType(value: unknown): void {
  draft.value = value == null ? '' : String(value)
}

function onBlur(): void {
  if (!focused.value) return
  focused.value = false
  emit('update:modelValue', parseNumber(draft.value))
}

const rangeClass = computed(() => {
  const range = baseNormalRange(props.field)
  if (numericValue.value == null || !range) return ''
  const { min, max } = range
  const abnormal =
    (min != null && numericValue.value < min) || (max != null && numericValue.value > max)
  return abnormal ? 'range-abnormal' : 'range-normal'
})
</script>

<style scoped>
.range-normal :deep(.p-inputtext) {
  border-color: var(--color-success);
}
.range-abnormal :deep(.p-inputtext) {
  border-color: var(--color-danger);
  background-color: color-mix(in srgb, var(--color-danger) 6%, transparent);
}
</style>
