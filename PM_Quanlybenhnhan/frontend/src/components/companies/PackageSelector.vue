<template>
  <div>
    <LoadingSkeleton v-if="loading" type="card" :rows="1" />
    <template v-else-if="packages.length === 0">
      <p class="text-sm text-text-muted">Công ty chưa có gói khám nào</p>
    </template>
    <div v-else class="flex flex-wrap gap-2">
      <button
        v-for="pkg in packages"
        :key="pkg.id"
        type="button"
        class="rounded-full border px-3 py-1.5 text-sm font-medium transition-colors"
        :class="
          isSelected(pkg.id)
            ? 'border-primary bg-primary text-white'
            : 'border-gray-300 bg-white text-text-body hover:border-primary'
        "
        @click="toggle(pkg.id)"
      >
        {{ pkg.package_detail?.name || pkg.exam_package }}
        <span class="ml-1 text-xs opacity-80">
          ({{ examTypeLabel(pkg.package_detail?.exam_type || 'periodic') }})
        </span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import { packagesService } from '@/services/packages'
import { examTypeLabel } from '@/utils/format'
import type { CompanyExamPackage } from '@/types'

const props = defineProps<{
  companyId: string
  modelValue: string[]
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const packages = ref<CompanyExamPackage[]>([])
const loading = ref(false)

function isSelected(id: string): boolean {
  return props.modelValue.includes(id)
}

function toggle(id: string): void {
  const next = props.modelValue.includes(id)
    ? props.modelValue.filter((x) => x !== id)
    : [...props.modelValue, id]
  emit('update:modelValue', next)
}

interface PaginatedResponse {
  results?: CompanyExamPackage[]
}

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await packagesService.listCompanyPackages(props.companyId)
    const all: CompanyExamPackage[] = Array.isArray(data)
      ? data
      : ((data as PaginatedResponse).results ?? [])
    packages.value = all.filter((p) => p.is_active)
  } finally {
    loading.value = false
  }
})
</script>
