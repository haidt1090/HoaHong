<template>
  <div class="flex flex-col gap-2">
    <label
      class="flex cursor-pointer items-center gap-2 rounded-md border border-gray-200 p-3 hover:border-primary"
    >
      <RadioButton :model-value="modelValue" value="package_total" @update:model-value="emit" />
      <div>
        <div class="text-sm font-medium">Theo giá trọn gói</div>
        <div class="text-xs text-text-muted">Một mức giá cố định cho toàn bộ gói khám</div>
      </div>
    </label>
    <label
      class="flex cursor-pointer items-center gap-2 rounded-md border border-gray-200 p-3 hover:border-primary"
    >
      <RadioButton :model-value="modelValue" value="per_field" @update:model-value="emit" />
      <div>
        <div class="text-sm font-medium">Theo từng chỉ số</div>
        <div class="text-xs text-text-muted">Tính giá theo từng chỉ số của các khoa</div>
      </div>
    </label>
  </div>
</template>

<script setup lang="ts">
import RadioButton from 'primevue/radiobutton'
import type { PricingMode } from '@/types'

defineProps<{ modelValue: PricingMode }>()
const emitEvent = defineEmits<{ 'update:modelValue': [value: PricingMode] }>()

function emit(value: PricingMode): void {
  emitEvent('update:modelValue', value)
}
</script>
