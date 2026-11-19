<template>
  <Tag v-if="label" :value="label" :severity="severity" :class="{ 'text-xs': size === 'sm' }" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Tag from 'primevue/tag'
import type { NormalRange } from '@/types'

const props = withDefaults(
  defineProps<{
    value: number | null | undefined
    range: NormalRange | null | undefined
    size?: 'sm' | 'md'
  }>(),
  { size: 'md' },
)

const severity = computed(() => {
  if (props.value == null || !props.range) return 'secondary'
  const { min, max } = props.range
  if (min != null && props.value < min) return 'danger'
  if (max != null && props.value > max) return 'danger'
  return 'success'
})

const label = computed(() => {
  if (!props.range) return null
  const { min, max } = props.range
  const parts: string[] = []
  if (min != null) parts.push(String(min))
  if (max != null) parts.push(String(max))
  if (parts.length === 2) return `${parts[0]}-${parts[1]}`
  if (min != null) return `>= ${min}`
  if (max != null) return `<= ${max}`
  return null
})
</script>
