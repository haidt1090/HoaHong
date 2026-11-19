import api from './api'
import type {
  Paginated,
  SyncConfig,
  SyncConfigInput,
  SyncConfigMap,
  SyncJob,
  SyncSigningXmlResult,
  SyncTriggerInput,
  SyncValidationResult,
} from '@/types'

export interface SyncJobListParams {
  status?: string
  scope_type?: string
  search?: string
  page?: number
  page_size?: number
}

export const nationalSyncService = {
  getConfig() {
    return api.get<SyncConfigMap>('/sync/config/')
  },

  updateConfig(payload: SyncConfigInput) {
    return api.put<SyncConfig>('/sync/config/', payload)
  },

  validate(payload: SyncTriggerInput) {
    return api.post<SyncValidationResult>('/sync/validate/', payload)
  },

  signingXml(payload: SyncTriggerInput) {
    return api.post<SyncSigningXmlResult>('/sync/signing-xml/', payload)
  },

  trigger(payload: SyncTriggerInput) {
    return api.post<SyncJob>('/sync/trigger/', payload)
  },

  listJobs(params: SyncJobListParams = {}) {
    return api.get<Paginated<SyncJob>>('/sync/jobs/', { params })
  },

  getJob(id: string) {
    return api.get<SyncJob>(`/sync/jobs/${id}/`)
  },
}
