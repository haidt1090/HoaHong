import api from './api'
import type {
  Paginated,
  ExamListItem,
  Examination,
  ExaminationDetail,
  ExaminationInput,
  ExamFormData,
  DepartmentResultDetail,
  DepartmentResultInput,
} from '@/types'

export interface ExamListParams {
  search?: string
  patient?: string
  company?: string
  exam_type?: string
  status?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

export const examsService = {
  list(params: ExamListParams = {}) {
    return api.get<Paginated<ExamListItem>>('/examinations/', { params })
  },

  get(id: string) {
    return api.get<ExaminationDetail>(`/examinations/${id}/`)
  },

  getForm(id: string) {
    return api.get<ExamFormData>(`/examinations/${id}/form/`)
  },

  create(payload: ExaminationInput) {
    return api.post<Examination>('/examinations/', payload)
  },

  update(id: string, payload: Partial<Examination>) {
    return api.put<Examination>(`/examinations/${id}/`, payload)
  },

  updateStatus(id: string, status: string) {
    return api.patch<Examination>(`/examinations/${id}/status/`, { status })
  },

  remove(id: string) {
    return api.delete(`/examinations/${id}/`)
  },

  // Department results
  updateDepartmentResult(examId: string, deptId: string, payload: DepartmentResultInput) {
    return api.put<DepartmentResultDetail>(
      `/examinations/${examId}/departments/${deptId}/`,
      payload,
    )
  },

  completeDepartmentResult(examId: string, deptId: string) {
    return api.patch<DepartmentResultDetail>(
      `/examinations/${examId}/departments/${deptId}/complete/`,
    )
  },
}
