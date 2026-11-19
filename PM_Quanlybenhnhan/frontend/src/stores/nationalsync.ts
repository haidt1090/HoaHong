import { defineStore } from 'pinia'
import { ref } from 'vue'
import { nationalSyncService } from '@/services/nationalsync'
import type {
  SyncConfig,
  SyncConfigInput,
  SyncConfigMap,
  SyncJob,
  SyncTriggerInput,
  SyncValidationResult,
} from '@/types'

export const useNationalSyncStore = defineStore('nationalsync', () => {
  const configs = ref<SyncConfigMap>({})
  const configLoading = ref(false)

  const jobs = ref<SyncJob[]>([])
  const jobsTotal = ref(0)
  const jobsLoading = ref(false)

  async function fetchConfig(): Promise<void> {
    configLoading.value = true
    try {
      const { data } = await nationalSyncService.getConfig()
      configs.value = data
    } finally {
      configLoading.value = false
    }
  }

  async function saveConfig(payload: SyncConfigInput): Promise<SyncConfig> {
    const { data } = await nationalSyncService.updateConfig(payload)
    configs.value = { ...configs.value, [data.environment]: data }
    return data
  }

  async function fetchJobs(params: { page?: number; page_size?: number } = {}): Promise<void> {
    jobsLoading.value = true
    try {
      const { data } = await nationalSyncService.listJobs(params)
      jobs.value = data.results ?? []
      jobsTotal.value = data.count ?? jobs.value.length
    } finally {
      jobsLoading.value = false
    }
  }

  async function validate(payload: SyncTriggerInput): Promise<SyncValidationResult> {
    const { data } = await nationalSyncService.validate(payload)
    return data
  }

  async function trigger(payload: SyncTriggerInput): Promise<SyncJob> {
    const { data } = await nationalSyncService.trigger(payload)
    return data
  }

  return {
    configs,
    configLoading,
    jobs,
    jobsTotal,
    jobsLoading,
    fetchConfig,
    saveConfig,
    fetchJobs,
    validate,
    trigger,
  }
})
