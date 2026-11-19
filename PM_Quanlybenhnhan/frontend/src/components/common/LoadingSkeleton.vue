<template>
  <div>
    <div v-if="type === 'table'" class="flex flex-col gap-2">
      <Skeleton v-for="n in rows" :key="n" height="2.5rem" />
    </div>
    <div v-else-if="type === 'card'" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Skeleton v-for="n in rows" :key="n" height="8rem" />
    </div>
    <div v-else class="flex flex-col gap-4">
      <div v-for="n in rows" :key="n" class="flex flex-col gap-1.5">
        <Skeleton width="8rem" height="1rem" />
        <Skeleton height="2.5rem" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import Skeleton from 'primevue/skeleton'

withDefaults(
  defineProps<{
    rows?: number
    type?: 'table' | 'card' | 'form'
  }>(),
  { rows: 4, type: 'table' },
)
</script>
