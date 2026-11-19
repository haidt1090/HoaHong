import api from './api'
import type { Paginated, Company, CompanyDetail, CompanyInput } from '@/types'

export interface CompanyListParams {
  search?: string
  page?: number
  page_size?: number
}

export const companiesService = {
  list(params: CompanyListParams = {}) {
    return api.get<Paginated<Company>>('/companies/', { params })
  },
  get(id: string) {
    return api.get<CompanyDetail>(`/companies/${id}/`)
  },
  create(payload: CompanyInput) {
    return api.post<Company>('/companies/', payload)
  },
  update(id: string, payload: CompanyInput) {
    return api.put<Company>(`/companies/${id}/`, payload)
  },
  remove(id: string) {
    return api.delete(`/companies/${id}/`)
  },
}
