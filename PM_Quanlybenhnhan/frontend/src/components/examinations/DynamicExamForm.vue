<template>
  <div class="rounded-lg border border-gray-200 bg-white">
    <div v-if="$slots.header" class="border-b border-gray-100 px-4 py-3">
      <slot name="header" />
    </div>

    <Tabs v-model:value="activeTab" scrollable>
      <TabList>
        <Tab
          v-for="dept in sortedDepartments"
          :key="dept.result_id"
          :value="dept.result_id"
        >
          <div class="flex items-center gap-2" :class="{ 'opacity-60': !dept.editable }">
            <i
              v-if="dept.completed"
              class="pi pi-check-circle text-xs text-success"
            />
            <i
              v-else-if="!dept.editable"
              class="pi pi-lock text-xs text-text-muted"
            />
            <i v-else-if="dirtyTabs?.has(String(dept.result_id))" class="pi pi-circle-fill text-[6px] text-warning" />
            <span>{{ dept.department.name }}</span>
          </div>
        </Tab>
      </TabList>
      <TabPanels>
        <TabPanel v-for="dept in sortedDepartments" :key="dept.result_id" :value="dept.result_id">
          <div class="p-4">
            <DepartmentTab
              :department="dept"
              :template-snapshot="dept.template_snapshot"
              :data="dept.data"
              :editable="dept.editable"
              :completed="dept.completed"
              :dirty="!!(dirtyTabs?.has(String(dept.result_id)))"
              :saving="savingDept === dept.result_id"
              :gender="patientGender"
              @save="$emit('saveDept', dept.result_id, dept.data)"
              @update:data="(key, val) => $emit('updateData', dept.result_id, key, val)"
            />
          </div>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import DepartmentTab from './DepartmentTab.vue'
import type { FormDepartment, Gender } from '@/types'

const props = withDefaults(
  defineProps<{
    departments: FormDepartment[]
    dirtyTabs: Set<string> | null
    savingDept: string | null
    readonly?: boolean
    patientGender?: Gender | null
  }>(),
  { readonly: false, patientGender: null },
)

const sortedDepartments = computed(() =>
  [...props.departments]
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
    .map((d) => (props.readonly ? { ...d, editable: false } : d)),
)

defineEmits<{
  saveDept: [departmentId: string, data: Record<string, unknown>]
  updateData: [departmentId: string, key: string, value: unknown]
}>()

const activeTab = ref<string>('')

// Auto-select the first department (prefer the first editable one) once data loads.
watch(
  sortedDepartments,
  (depts) => {
    if (!depts.length) return
    const stillValid = depts.some((d) => String(d.result_id) === activeTab.value)
    if (activeTab.value && stillValid) return
    const firstEditable = depts.find((d) => d.editable)
    activeTab.value = String((firstEditable ?? depts[0]).result_id)
  },
  { immediate: true },
)
</script>
