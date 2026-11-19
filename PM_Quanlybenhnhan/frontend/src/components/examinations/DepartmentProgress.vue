<template>
  <div class="flex items-center gap-2">
    <div class="h-2 flex-1 overflow-hidden rounded-full bg-gray-200">
      <div
        class="h-full rounded-full transition-all duration-300"
        :class="percentage === 100 ? 'bg-success' : percentage > 0 ? 'bg-primary' : 'bg-gray-200'"
        :style="{ width: `${percentage}%` }"
      />
    </div>
    <span class="text-xs font-medium text-text-muted whitespace-nowrap">{{ percentage }}%</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  completed: number
  total: number
}>()

const percentage = computed(() => {
  if (props.total === 0) return 0
  return Math.round((props.completed / props.total) * 100)
})
</script>
