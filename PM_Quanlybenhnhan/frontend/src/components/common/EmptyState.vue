<template>
  <div class="flex flex-col items-center justify-center gap-3 py-16 text-center">
    <i :class="icon" class="text-5xl text-text-muted/50" />
    <h3 class="m-0 text-lg font-semibold text-text-body">{{ title }}</h3>
    <p v-if="description" class="m-0 max-w-md text-sm text-text-muted">{{ description }}</p>
    <Button v-if="actionLabel" :label="actionLabel" @click="$emit('action')" />
  </div>
</template>

<script setup lang="ts">
import Button from 'primevue/button'

withDefaults(
  defineProps<{
    icon?: string
    title: string
    description?: string
    actionLabel?: string
  }>(),
  { icon: 'pi pi-inbox', description: '', actionLabel: '' },
)

defineEmits<{ action: [] }>()
</script>
