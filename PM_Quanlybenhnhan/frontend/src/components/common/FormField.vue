<template>
  <div class="flex flex-col gap-1.5">
    <label v-if="label" class="text-sm font-semibold text-text-body">
      {{ label }}
      <span v-if="required" class="text-danger">*</span>
    </label>
    <slot />
    <small v-if="helpText && !error" class="text-text-muted">{{ helpText }}</small>
    <small v-if="error" class="text-danger">{{ error }}</small>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  label?: string
  required?: boolean
  error?: string
  helpText?: string
}>()
</script>
