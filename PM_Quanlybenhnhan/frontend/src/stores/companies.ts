import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { companiesService } from '@/services/companies'
import type { Company, CompanyDetail, CompanyInput } from '@/types'

interface CompanyFilters {
  search: string
  page: number
  page_size: number
}

export const useCompanyStore = defineStore('companies', () => {
  const list = ref<Company[]>([])
  const current = ref<CompanyDetail | null>(null)
  const totalRecords = ref(0)
  const loading = ref(false)
  const filters = reactive<CompanyFilters>({ search: '', page: 1, page_size: 20 })

  async function fetchList(): Promise<void> {
    loading.value = true
    try {
      const { data } = await companiesService.list({
        search: filters.search || undefined,
        page: filters.page,
        page_size: filters.page_size,
      })
      list.value = data.results ?? []
      totalRecords.value = data.count ?? list.value.length
    } finally {
      loading.value = false
    }
  }

  async function fetchById(id: string): Promise<CompanyDetail> {
    loading.value = true
    try {
      const { data } = await companiesService.get(id)
      current.value = data
      return data
    } finally {
      loading.value = false
    }
  }

  async function create(payload: CompanyInput): Promise<Company> {
    const { data } = await companiesService.create(payload)
    return data
  }

  async function update(id: string, payload: CompanyInput): Promise<Company> {
    const { data } = await companiesService.update(id, payload)
    return data
  }

  async function remove(id: string): Promise<void> {
    await companiesService.remove(id)
    list.value = list.value.filter((c) => c.id !== id)
  }

  return {
    list,
    current,
    totalRecords,
    loading,
    filters,
    fetchList,
    fetchById,
    create,
    update,
    remove,
  }
})
