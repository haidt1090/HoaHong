import { defineStore } from 'pinia'
import { ref } from 'vue'
import { packagesService } from '@/services/packages'
import type { ExamPackage, CompanyExamPackage, CompanyExamPackageInput } from '@/types'

function unwrap<T>(data: { results: T[] } | T[]): T[] {
  return Array.isArray(data) ? data : data.results
}

export const usePackageStore = defineStore('packages', () => {
  const examPackages = ref<ExamPackage[]>([])
  const companyPackages = ref<Record<string, CompanyExamPackage[]>>({})
  const loading = ref(false)

  async function fetchExamPackages(): Promise<void> {
    const { data } = await packagesService.listExamPackages()
    examPackages.value = unwrap(data)
  }

  async function fetchCompanyPackages(companyId: string): Promise<void> {
    loading.value = true
    try {
      const { data } = await packagesService.listCompanyPackages(companyId)
      companyPackages.value[companyId] = unwrap(data)
    } finally {
      loading.value = false
    }
  }

  async function assignPackage(
    companyId: string,
    payload: CompanyExamPackageInput,
  ): Promise<CompanyExamPackage> {
    const { data } = await packagesService.assign(companyId, payload)
    await fetchCompanyPackages(companyId)
    return data
  }

  async function updatePackage(
    companyId: string,
    pkgId: string,
    payload: Partial<CompanyExamPackageInput>,
  ): Promise<CompanyExamPackage> {
    const { data } = await packagesService.update(companyId, pkgId, payload)
    await fetchCompanyPackages(companyId)
    return data
  }

  async function deactivatePackage(companyId: string, pkgId: string): Promise<void> {
    await packagesService.deactivate(companyId, pkgId)
    await fetchCompanyPackages(companyId)
  }

  return {
    examPackages,
    companyPackages,
    loading,
    fetchExamPackages,
    fetchCompanyPackages,
    assignPackage,
    updatePackage,
    deactivatePackage,
  }
})
