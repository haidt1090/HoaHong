import api from './api'
import type {
  Paginated,
  Patient,
  PatientDetail,
  PatientInput,
  PatientReportLink,
} from '@/types'

export interface PatientListParams {
  search?: string
  company?: string | null
  has_company?: boolean
  is_active?: boolean
  page?: number
  page_size?: number
  ordering?: string
}

export const patientsService = {
  list(params: PatientListParams = {}) {
    return api.get<Paginated<Patient>>('/patients/', { params })
  },
  get(id: string) {
    return api.get<PatientDetail>(`/patients/${id}/`)
  },
  create(payload: PatientInput) {
    return api.post<Patient>('/patients/', payload)
  },
  update(id: string, payload: PatientInput) {
    return api.put<Patient>(`/patients/${id}/`, payload)
  },
  remove(id: string) {
    return api.delete(`/patients/${id}/`)
  },
  import(formData: FormData) {
    return api.post<{ created?: number; skipped?: number; errors?: { row: number; message: string }[]; error?: string }>(
      '/patients/import/',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
  },
  downloadTemplate() {
    return api.get('/patients/import-template/', { responseType: 'blob' })
  },

  /** Get public report links (URL + password) for a company's employees. */
  reportLinks(companyId: string) {
    return api.get<Record<string, PatientReportLink>>('/patients/report-links/', {
      params: { company_id: companyId },
    })
  },

  /** Get or create a public report link for a single patient. */
  reportLink(patientId: string) {
    return api.get<{ url: string; password: string; status: string }>(
      `/patients/${patientId}/report-link/`,
    )
  },
}