import api from './api'
import type { DiagnosisKeyword, DiagnosisKeywordInput, DiagnosisResponse, FindingsResponse, Paginated } from '@/types'

export interface KeywordListParams {
  search?: string
  disease_name?: string
  classification?: number
  is_active?: boolean
  page?: number
  page_size?: number
  ordering?: string
}

export const diagnosisService = {
  // Keywords
  listKeywords(params: KeywordListParams = {}) {
    return api.get<Paginated<DiagnosisKeyword>>('/diagnosis/keywords/', { params })
  },

  getKeyword(id: string) {
    return api.get<DiagnosisKeyword>(`/diagnosis/keywords/${id}/`)
  },

  createKeyword(payload: DiagnosisKeywordInput) {
    return api.post<DiagnosisKeyword>('/diagnosis/keywords/', payload)
  },

  updateKeyword(id: string, payload: Partial<DiagnosisKeywordInput>) {
    return api.put<DiagnosisKeyword>(`/diagnosis/keywords/${id}/`, payload)
  },

  removeKeyword(id: string) {
    return api.delete(`/diagnosis/keywords/${id}/`)
  },

  importKeywords(file: File, mode: 'append' | 'replace' = 'append') {
    const form = new FormData()
    form.append('file', file)
    form.append('mode', mode)
    return api.post<{ diseases_created: number; keywords_created: number }>(
      '/diagnosis/keywords/import-keywords/',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
  },

  // Findings
  getFindings(examId: string) {
    return api.get<FindingsResponse>(`/examinations/${examId}/findings/`)
  },

  // Diagnosis (server-side keyword matching)
  getDiagnosis(examId: string) {
    return api.get<DiagnosisResponse>(`/examinations/${examId}/diagnosis/`)
  },

  downloadKeywordTemplate() {
    return api.get('/diagnosis/keywords/import-template/', { responseType: 'blob' })
  },
}
