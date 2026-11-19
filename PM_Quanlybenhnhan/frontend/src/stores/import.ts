import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { importService } from '@/services/import'
import type { ImportJob } from '@/types'

export const useImportStore = defineStore('import', () => {
  const currentJob = ref<ImportJob | null>(null)
  const loading = ref(false)

  const currentImport = computed(() => currentJob.value)
  const importing = computed(() => loading.value)

  async function startImport(departmentId: string, formData: FormData): Promise<ImportJob> {
    loading.value = true
    try {
      const { data } = await importService.upload(departmentId, formData)
      currentJob.value = data
      return data
    } finally {
      loading.value = false
    }
  }

  async function pollStatus(jobId: string): Promise<ImportJob> {
    const { data } = await importService.getStatus(jobId)
    currentJob.value = data
    return data
  }

  function reset() {
    currentJob.value = null
    loading.value = false
  }

  return { currentJob, currentImport, loading, importing, startImport, pollStatus, reset }
})
