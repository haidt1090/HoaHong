import api from './api'
import type {
  DepartmentReportTemplate,
  GenerateReportInput,
  Paginated,
  Report,
  ReportTemplate,
  ReportTemplateSummary,
  TemplatePreviewInput,
  TemplateVariablesResponse,
} from '@/types'

export interface ReportListParams {
  report_type?: string
  status?: string
  page?: number
  page_size?: number
}

export interface ReportTemplateListParams {
  report_type?: string
  body_type?: string
  is_active?: boolean
  page_size?: number
}

export const reportsService = {
  list(params: ReportListParams = {}) {
    return api.get<Paginated<Report>>('/reports/', { params })
  },

  get(id: string) {
    return api.get<Report>(`/reports/${id}/`)
  },

  remove(id: string) {
    return api.delete(`/reports/${id}/`)
  },

  generate(payload: GenerateReportInput) {
    return api.post<Report>('/reports/generate/', payload)
  },

  download(id: string) {
    return api.get(`/reports/${id}/download/`, { responseType: 'blob' })
  },
}

export const reportTemplatesService = {
  list(params: ReportTemplateListParams = {}) {
    return api.get<Paginated<ReportTemplateSummary>>('/report-templates/', { params })
  },

  get(id: string) {
    return api.get<ReportTemplate>(`/report-templates/${id}/`)
  },

  create(payload: Partial<ReportTemplate>) {
    return api.post<ReportTemplate>('/report-templates/', payload)
  },

  update(id: string, payload: Partial<ReportTemplate>) {
    return api.patch<ReportTemplate>(`/report-templates/${id}/`, payload)
  },

  remove(id: string) {
    return api.delete(`/report-templates/${id}/`)
  },

  /** Documented shortcodes for the template editor's variable picker. */
  variables() {
    return api.get<TemplateVariablesResponse>('/report-templates/variables/')
  },

  /** Returns raw HTML — not JSON. */
  preview(id: string, payload: TemplatePreviewInput = {}) {
    return api.post<string>(`/report-templates/${id}/preview/`, payload, {
      responseType: 'text',
    })
  },
}

export const departmentReportTemplatesService = {
  list(params: { department?: string; is_active?: boolean; page_size?: number } = {}) {
    return api.get<Paginated<DepartmentReportTemplate>>('/department-report-templates/', {
      params,
    })
  },

  get(id: string) {
    return api.get<DepartmentReportTemplate>(`/department-report-templates/${id}/`)
  },

  create(payload: Partial<DepartmentReportTemplate>) {
    return api.post<DepartmentReportTemplate>('/department-report-templates/', payload)
  },

  update(id: string, payload: Partial<DepartmentReportTemplate>) {
    return api.patch<DepartmentReportTemplate>(
      `/department-report-templates/${id}/`,
      payload,
    )
  },

  remove(id: string) {
    return api.delete(`/department-report-templates/${id}/`)
  },

  preview(id: string, payload: TemplatePreviewInput = {}) {
    return api.post<string>(`/department-report-templates/${id}/preview/`, payload, {
      responseType: 'text',
    })
  },
}
