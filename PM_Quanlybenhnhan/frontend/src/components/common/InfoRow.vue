<template>
  <div class="flex border-b border-gray-100 py-2 last:border-b-0">
    <dt class="w-36 flex-shrink-0 text-sm text-text-muted">{{ label }}</dt>
    <dd class="m-0 text-sm text-text-body">{{ displayValue }}</dd>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  value?: string | number | null
}>()

const displayValue = computed(() => {
  if (props.value === null || props.value === undefined || props.value === '') return '--'
  return String(props.value)
})
</script>
