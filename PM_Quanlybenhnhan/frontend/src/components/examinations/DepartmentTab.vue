<template>
  <div>
    <div class="mb-4 flex items-center justify-between">
      <h3 class="m-0 text-lg font-semibold text-text-body">
        {{ department.department.name ?? department.department_detail?.name }}
        <i v-if="!editable" class="pi pi-lock ml-2 text-sm text-text-muted" />
        <Tag v-if="completed" value="Hoàn thành" severity="success" class="ml-2" />
      </h3>
      <Button
        v-if="editable && dirty"
        :label="saving ? 'Đang lưu...' : 'Lưu'"
        icon="pi pi-save"
        :loading="!!saving"
        @click="$emit('save')"
      />
    </div>
    <FieldTable
      :fields="templateSnapshot"
      :model-value="data"
      :editable="editable"
      :gender="gender"
      @update:model-value="onFieldChange"
    />
  </div>
</template>

<script setup lang="ts">
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import FieldTable from './FieldTable.vue'
import type { Department, FieldDefinition, Gender } from '@/types'

defineProps<{
  department: { department: Department; department_detail?: Department }
  templateSnapshot: FieldDefinition[]
  data: Record<string, unknown>
  editable: boolean
  completed: boolean
  dirty: boolean
  saving: boolean | string
  gender?: Gender | null
}>()

const emit = defineEmits<{
  save: []
  'update:data': [key: string, value: unknown]
}>()

function onFieldChange(key: string, value: unknown) {
  emit('update:data', key, value)
}
</script>
