<template>
  <div class="relative border-l-2 border-gray-200 pl-6">
    <div v-if="items.length === 0" class="py-6 text-sm text-text-muted">Chưa có lịch sử khám</div>
    <div v-for="exam in items" :key="exam.id" class="relative mb-6 last:mb-0">
      <span class="absolute -left-[1.9rem] top-1 h-3 w-3 rounded-full bg-primary" />
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-xs text-text-muted">{{ exam.exam_date }}</span>
        <StatusBadge :status="exam.status" size="sm" />
      </div>
      <div class="mt-1 font-semibold text-text-body">{{ examTypeLabel(exam.exam_type) }}</div>
      <p v-if="exam.conclusion" class="m-0 mt-1 text-sm text-text-muted">{{ exam.conclusion }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import StatusBadge from '@/components/common/StatusBadge.vue'
import { examTypeLabel } from '@/utils/format'
import type { ExamSummary } from '@/types'

defineProps<{ items: ExamSummary[] }>()
</script>
