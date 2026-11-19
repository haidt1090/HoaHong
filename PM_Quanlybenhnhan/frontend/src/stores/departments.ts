import { defineStore } from 'pinia'
import { ref } from 'vue'
import { departmentsService } from '@/services/departments'
import type { Department, DepartmentTemplate } from '@/types'

export const useDepartmentStore = defineStore('departments', () => {
  const list = ref<Department[]>([])
  const templates = ref<Record<string, DepartmentTemplate>>({})
  const loading = ref(false)

  async function fetchDepartments(): Promise<void> {
    loading.value = true
    try {
      const { data } = await departmentsService.list()
      list.value = Array.isArray(data) ? data : []
    } finally {
      loading.value = false
    }
  }

  async function fetchTemplate(templateId: string): Promise<DepartmentTemplate> {
    const { data } = await departmentsService.getTemplate(templateId)
    templates.value[templateId] = data
    return data
  }

  return {
    list,
    templates,
    loading,
    fetchDepartments,
    fetchTemplate,
  }
})
