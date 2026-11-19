import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { reportsService, type ReportListParams } from '@/services/reports'
import type { Report, GenerateReportInput } from '@/types'

interface ReportFilters {
  report_type: string | null
  page: number
  page_size: number
}

export const useReportStore = defineStore('reports', () => {
  const list = ref<Report[]>([])
  const totalRecords = ref(0)
  const loading = ref(false)

  const filters = reactive<ReportFilters>({
    report_type: null,
    page: 1,
    page_size: 20,
  })

  async function fetchList(): Promise<void> {
    loading.value = true
    try {
      const params: ReportListParams = {
        report_type: filters.report_type || undefined,
        page: filters.page,
        page_size: filters.page_size,
      }
      const { data } = await reportsService.list(params)
      list.value = data.results ?? []
      totalRecords.value = data.count ?? list.value.length
    } finally {
      loading.value = false
    }
  }

  async function fetchById(id: string): Promise<Report> {
    const { data } = await reportsService.get(id)
    return data
  }

  async function generate(payload: GenerateReportInput): Promise<Report> {
    const { data } = await reportsService.generate(payload)
    return data
  }

  async function remove(id: string): Promise<void> {
    await reportsService.remove(id)
    list.value = list.value.filter((r) => r.id !== id)
    totalRecords.value = Math.max(0, totalRecords.value - 1)
  }

  function resetFilters(): void {
    filters.report_type = null
    filters.page = 1
  }

  return {
    list,
    totalRecords,
    loading,
    filters,
    fetchList,
    fetchById,
    generate,
    remove,
    resetFilters,
  }
})
