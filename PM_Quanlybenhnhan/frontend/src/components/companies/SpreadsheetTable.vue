<template>
  <div class="spreadsheet-wrapper overflow-x-auto rounded-lg border border-gray-200">
    <table class="border-collapse text-sm">
      <!-- Row 1: Column headers -->
      <tr class="bg-gray-50">
        <th class="sticky left-0 z-10 min-w-[6rem] border-b border-r border-gray-200 bg-gray-50 px-3 py-2 text-left text-xs font-medium text-text-muted"></th>
        <th
          v-for="field in sortedFields"
          :key="field.key"
          class="min-w-[7rem] border-b border-r border-gray-200 px-3 py-2 text-center text-xs font-semibold text-text-body"
        >
          {{ field.label }}
          <span v-if="isComputedField(field)" class="text-[10px] text-text-muted"> (tự động)</span>
          <span v-if="field.unit" class="text-text-muted"> ({{ field.unit }})</span>
        </th>
      </tr>

      <!-- Row 2: Input cells -->
      <tr>
        <td class="sticky left-0 z-10 border-b border-r border-gray-200 bg-white px-3 py-2 text-xs font-medium text-text-muted">
          Kết quả
        </td>
        <td
          v-for="field in sortedFields"
          :key="field.key"
          class="border-b border-r border-gray-200 px-2 py-1 align-top"
          :class="{ 'bg-gray-100': isComputedField(field) }"
          :data-field-last="isLastEditable(field) ? 'true' : undefined"
        >
          <component
            :is="fieldRenderer(field.type)"
            :field="field"
            :model-value="valueFor(field)"
            :disabled="disabled || isComputedField(field)"
            @update:model-value="(v: unknown) => onChange(field.key, v)"
          />
        </td>
      </tr>

      <!-- Row 3: Normal range reference -->
      <tr>
        <td class="sticky left-0 z-10 border-r border-gray-200 bg-white px-3 py-2 text-xs font-medium text-text-muted">
          BT
        </td>
        <td
          v-for="field in sortedFields"
          :key="field.key"
          class="border-r border-gray-200 px-3 py-2 text-center"
        >
          <template v-if="baseNormalRange(field)">
            <span
              class="rounded px-1.5 py-0.5 text-xs font-medium"
              :class="rangeClass(field)"
            >
              {{ formatRange(baseNormalRange(field)!) }}
            </span>
          </template>
          <span v-else class="text-xs text-text-muted">--</span>
        </td>
      </tr>
    </table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FieldDefinition, Gender, NormalRange } from '@/types'
import { baseNormalRange, isComputedField, fieldAppliesToGender } from '@/utils/field'
import { evaluateComputedFields } from '@/utils/formula'
import TextField from '@/components/examinations/fields/TextField.vue'
import NumberField from '@/components/examinations/fields/NumberField.vue'
import SelectField from '@/components/examinations/fields/SelectField.vue'
import MultiSelectField from '@/components/examinations/fields/MultiSelectField.vue'
import BooleanField from '@/components/examinations/fields/BooleanField.vue'
import DateField from '@/components/examinations/fields/DateField.vue'
import TextareaField from '@/components/examinations/fields/TextareaField.vue'

const props = defineProps<{
  fields: FieldDefinition[]
  modelValue: Record<string, unknown>
  disabled?: boolean
  gender?: Gender | null
}>()

const emit = defineEmits<{
  'update:modelValue': [key: string, value: unknown]
}>()

const sortedFields = computed(() =>
  [...props.fields]
    .filter((f) => fieldAppliesToGender(f, props.gender))
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0)),
)

const computedValues = computed(() =>
  evaluateComputedFields(sortedFields.value, props.modelValue, props.gender),
)

const editableFields = computed(() =>
  sortedFields.value.filter((f) => !isComputedField(f)),
)

function valueFor(field: FieldDefinition): unknown {
  if (isComputedField(field)) return computedValues.value[field.key]
  return props.modelValue[field.key]
}

function isLastEditable(field: FieldDefinition): boolean {
  const editable = editableFields.value
  return editable.length > 0 && editable[editable.length - 1].key === field.key
}

type RendererMap = Record<string, unknown>
const renderers: RendererMap = {
  text: TextField,
  number: NumberField,
  select: SelectField,
  'multi-select': MultiSelectField,
  boolean: BooleanField,
  date: DateField,
  textarea: TextareaField,
  computed: NumberField,
}

function fieldRenderer(type: string) {
  return renderers[type] ?? TextField
}

function onChange(key: string, value: unknown) {
  emit('update:modelValue', key, value)
}

function normalRangeValue(field: FieldDefinition): number | null {
  const val = valueFor(field)
  if (val === null || val === undefined || val === '') return null
  const n = Number(val)
  return isNaN(n) ? null : n
}

function formatRange(range: NormalRange): string {
  const min = range.min != null ? String(range.min) : ''
  const max = range.max != null ? String(range.max) : ''
  if (min && max) return `${min} - ${max}`
  if (min) return `≥ ${min}`
  if (max) return `≤ ${max}`
  return ''
}

function rangeClass(field: FieldDefinition): string {
  const val = normalRangeValue(field)
  const range = baseNormalRange(field)
  if (val == null || !range) return 'bg-gray-100 text-text-muted'
  const { min, max } = range
  if ((min != null && val < min) || (max != null && val > max)) {
    return 'bg-red-50 text-danger'
  }
  return 'bg-green-50 text-success'
}
</script>
