import api from './api'
import type { ImportJob } from '@/types'

export interface ExportRequest {
  company_id: string
  package_id: string
  department_id: string
  exam_date?: string
  mode?: 'all' | 'pending'
}

export interface ExportStatus {
  id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress?: { current: number; total: number } | string | null
}

export const importService = {
  upload(departmentId: string, formData: FormData) {
    return api.post<ImportJob>(`/examinations/import/${departmentId}/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  getStatus(jobId: string) {
    return api.get<ImportJob>(`/import/${jobId}/`)
  },

  startExport(payload: ExportRequest) {
    return api.post<ExportStatus>('/export/', payload)
  },

  getExportStatus(exportId: string) {
    return api.get<ExportStatus>(`/export/${exportId}/`)
  },

  downloadExport(exportId: string) {
    return api.get(`/export/${exportId}/download/`, { responseType: 'blob' })
  },
}
