import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { patientsService } from '@/services/patients'
import type { Patient, PatientDetail, PatientInput } from '@/types'

interface PatientFilters {
  search: string
  company: string | null
  page: number
  page_size: number
}

export const usePatientStore = defineStore('patients', () => {
  const list = ref<Patient[]>([])
  const current = ref<PatientDetail | null>(null)
  const totalRecords = ref(0)
  const loading = ref(false)
  const filters = reactive<PatientFilters>({
    search: '',
    company: null,
    page: 1,
    page_size: 20,
  })

  async function fetchList(): Promise<void> {
    loading.value = true
    try {
      const { data } = await patientsService.list({
        search: filters.search || undefined,
        company: filters.company || undefined,
        page: filters.page,
        page_size: filters.page_size,
      })
      list.value = data.results ?? []
      totalRecords.value = data.count ?? list.value.length
    } finally {
      loading.value = false
    }
  }

  async function fetchById(id: string): Promise<PatientDetail> {
    loading.value = true
    try {
      const { data } = await patientsService.get(id)
      current.value = data
      return data
    } finally {
      loading.value = false
    }
  }

  async function create(payload: PatientInput): Promise<Patient> {
    const { data } = await patientsService.create(payload)
    return data
  }

  async function update(id: string, payload: PatientInput): Promise<Patient> {
    const { data } = await patientsService.update(id, payload)
    return data
  }

  async function remove(id: string): Promise<void> {
    await patientsService.remove(id)
    list.value = list.value.filter((p) => p.id !== id)
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
