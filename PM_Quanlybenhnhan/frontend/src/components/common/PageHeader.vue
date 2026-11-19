<template>
  <div class="mb-6 flex flex-wrap items-end justify-between gap-4">
    <div>
      <Breadcrumb
        v-if="breadcrumb.length > 1"
        :model="breadcrumb"
        :pt="{ root: { class: 'mb-1 bg-transparent p-0 text-sm' } }"
      >
        <template #item="{ item }">
          <router-link v-if="item.to" :to="item.to" class="text-text-muted hover:text-primary">
            {{ item.label }}
          </router-link>
          <span v-else class="text-text-body">{{ item.label }}</span>
        </template>
      </Breadcrumb>
      <h1 class="m-0 text-2xl font-bold text-text-body">{{ title }}</h1>
      <p v-if="subtitle" class="m-0 mt-1 text-sm text-text-muted">{{ subtitle }}</p>
    </div>
    <div class="flex items-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import Breadcrumb from 'primevue/breadcrumb'
import { useBreadcrumb } from '@/composables/useBreadcrumb'

defineProps<{
  title: string
  subtitle?: string
}>()

const { items: breadcrumb } = useBreadcrumb()
</script>
