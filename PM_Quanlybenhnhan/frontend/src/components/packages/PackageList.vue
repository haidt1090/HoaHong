<template>
  <div>
    <EmptyState
      v-if="packages.length === 0"
      icon="pi pi-box"
      title="Chưa có gói khám"
      description="Chưa có gói khám nào được gán cho công ty này."
    />
    <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <PackageCard
        v-for="pkg in packages"
        :key="pkg.id"
        :pkg="pkg"
        @edit="$emit('edit', pkg)"
        @deactivate="$emit('deactivate', pkg)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import PackageCard from './PackageCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import type { CompanyExamPackage } from '@/types'

defineProps<{ packages: CompanyExamPackage[] }>()

defineEmits<{
  edit: [pkg: CompanyExamPackage]
  deactivate: [pkg: CompanyExamPackage]
}>()
</script>
