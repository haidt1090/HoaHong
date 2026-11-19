<template>
  <div class="overflow-x-auto">
    <table class="w-full border-collapse text-sm">
      <thead>
        <tr class="border-b border-gray-200 bg-gray-50">
          <th class="px-3 py-2 text-left font-semibold text-text-body">Chỉ số</th>
          <th class="px-3 py-2 text-left font-semibold text-text-body">Kết quả</th>
          <th class="px-3 py-2 text-center font-semibold text-text-body">Đơn vị</th>
          <th class="px-3 py-2 text-center font-semibold text-text-body">Khoảng bình thường</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="field in sortedFields"
          :key="field.key"
          class="border-b border-gray-100 transition-colors hover:bg-gray-50"
        >
          <td class="px-3 py-2">
            <span class="font-medium">{{ field.label }}</span>
            <span v-if="isComputedField(field)" class="ml-1 text-[10px] text-text-muted">(tự động)</span>
            <span v-if="field.required" class="ml-1 text-danger">*</span>
          </td>
          <td class="px-3 py-2" :class="{ 'bg-gray-100': isComputedField(field) }">
            <component
              :is="fieldRenderer(field.type)"
              :field="field"
              :model-value="valueFor(field)"
              :disabled="!editable || isComputedField(field)"
              @update:model-value="onChange(field.key, $event)"
            />
          </td>
          <td class="px-3 py-2 text-center text-text-muted">{{ field.unit || '--' }}</td>
          <td class="px-3 py-2 text-center">
            <NormalRangeBadge
              :value="normalRangeValue(field)"
              :range="baseNormalRange(field)"
              size="sm"
            />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FieldDefinition, Gender } from '@/types'
import { baseNormalRange, isComputedField, fieldAppliesToGender } from '@/utils/field'
import { evaluateComputedFields } from '@/utils/formula'
import TextField from './fields/TextField.vue'
import NumberField from './fields/NumberField.vue'
import SelectField from './fields/SelectField.vue'
import MultiSelectField from './fields/MultiSelectField.vue'
import BooleanField from './fields/BooleanField.vue'
import DateField from './fields/DateField.vue'
import TextareaField from './fields/TextareaField.vue'
import NormalRangeBadge from './NormalRangeBadge.vue'

const props = defineProps<{
  fields: FieldDefinition[]
  modelValue: Record<string, unknown>
  editable: boolean
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

function valueFor(field: FieldDefinition): unknown {
  if (isComputedField(field)) return computedValues.value[field.key]
  return props.modelValue[field.key]
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
</script>
