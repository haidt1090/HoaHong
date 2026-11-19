import api from './api'
import type {
  Paginated,
  ExamPackage,
  CompanyExamPackage,
  CompanyExamPackageInput,
  DepartmentTemplate,
} from '@/types'

export const packagesService = {
  listExamPackages() {
    return api.get<Paginated<ExamPackage> | ExamPackage[]>('/packages/', {
      params: { is_active: true },
    })
  },
  getExamPackage(id: string) {
    return api.get<ExamPackage>(`/packages/${id}/`)
  },
  getTemplate(id: string) {
    return api.get<DepartmentTemplate>(`/templates/${id}/`)
  },
  listCompanyPackages(companyId: string) {
    return api.get<Paginated<CompanyExamPackage> | CompanyExamPackage[]>(
      `/companies/${companyId}/packages/`,
    )
  },
  assign(companyId: string, payload: CompanyExamPackageInput) {
    return api.post<CompanyExamPackage>(`/companies/${companyId}/packages/`, payload)
  },
  update(companyId: string, pkgId: string, payload: Partial<CompanyExamPackageInput>) {
    return api.put<CompanyExamPackage>(`/companies/${companyId}/packages/${pkgId}/`, payload)
  },
  deactivate(companyId: string, pkgId: string) {
    return api.delete(`/companies/${companyId}/packages/${pkgId}/`)
  },
}
