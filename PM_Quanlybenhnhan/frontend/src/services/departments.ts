import api from './api'
import type { Department, DepartmentTemplate } from '@/types'

export const departmentsService = {
  list() {
    return api.get<Department[]>('/departments/')
  },

  listTemplates(departmentId?: string) {
    const params = departmentId ? { department: departmentId } : {}
    return api.get<DepartmentTemplate[]>('/templates/', { params })
  },

  getTemplate(id: string) {
    return api.get<DepartmentTemplate>(`/templates/${id}/`)
  },

  renderTemplate(id: string) {
    return api.get<{ fields_config: DepartmentTemplate['fields_config'] }>(
      `/templates/${id}/render/`,
    )
  },

  exportTemplate(id: string) {
    return api.get(`/templates/${id}/export-template/`, { responseType: 'blob' })
  },
}
