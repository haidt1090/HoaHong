<template>
  <div>
    <div ref="searchWrap" class="relative">
      <InputText
        v-model="query"
        placeholder="Tìm theo tên hoặc mã nhân viên..."
        class="w-full"
        @input="debounceSearch"
        @keydown.enter="selectFirst"
      />
      <i
        v-if="query && !searching"
        class="pi pi-times absolute right-2 top-1/2 -translate-y-1/2 cursor-pointer text-text-muted hover:text-text-body"
        @click="clearSearch"
      />
    </div>

    <ul
      v-if="suggestions.length && query"
      class="mt-1 max-h-56 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg"
    >
      <li
        v-for="(p, i) in suggestions"
        :key="p.id"
        class="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-primary/5"
        :class="{ 'bg-primary/10': i === activeIndex }"
        @click="select(p)"
        @mouseenter="activeIndex = i"
      >
        <span class="text-xs text-text-muted">{{ p.employee_code || '--' }}</span>
        <span class="font-medium">{{ p.full_name }}</span>
      </li>
      <li v-if="!searching && suggestions.length === 0" class="px-3 py-2 text-sm text-text-muted">
        Không tìm thấy nhân viên
      </li>
    </ul>

    <Chip
      v-if="selected"
      :label="`${selected.employee_code || '--'} - ${selected.full_name}`"
      removable
      class="mt-2"
      @remove="clearSelection"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import InputText from 'primevue/inputtext'
import Chip from 'primevue/chip'
import { patientsService } from '@/services/patients'
import type { Patient } from '@/types'

const props = defineProps<{ companyId: string; preSelectedId?: string | null }>()
const emit = defineEmits<{ select: [patient: Patient] }>()

const query = ref('')
const searching = ref(false)
const suggestions = ref<Patient[]>([])
const activeIndex = ref(-1)
const selected = ref<Patient | null>(null)
const searchWrap = ref<HTMLElement | null>(null)
let timer: ReturnType<typeof setTimeout>

watch(
  () => props.preSelectedId,
  async (id) => {
    if (id) {
      try {
        const { data } = await patientsService.get(id)
        selected.value = data as unknown as Patient
      } catch {
        // ignore
      }
    }
  },
  { immediate: true },
)

async function debounceSearch(): Promise<void> {
  clearTimeout(timer)
  if (!query.value.trim()) {
    suggestions.value = []
    return
  }
  timer = setTimeout(async () => {
    searching.value = true
    try {
      const { data } = await patientsService.list({
        search: query.value,
        company: props.companyId,
        is_active: true,
        page_size: 20,
      })
      suggestions.value = Array.isArray(data.results) ? data.results : (data as unknown as Patient[])
      activeIndex.value = -1
    } finally {
      searching.value = false
    }
  }, 300)
}

function select(patient: Patient): void {
  selected.value = patient
  suggestions.value = []
  query.value = ''
  emit('select', patient)
}

function selectFirst(): void {
  if (suggestions.value.length > 0) {
    const idx = activeIndex.value >= 0 ? activeIndex.value : 0
    select(suggestions.value[idx])
  }
}

function clearSearch(): void {
  query.value = ''
  suggestions.value = []
}

function clearSelection(): void {
  selected.value = null
}

function focusSearch(): void {
  const input = searchWrap.value?.querySelector('input') as HTMLElement | null
  input?.focus()
}

defineExpose({ focusSearch })
</script>
