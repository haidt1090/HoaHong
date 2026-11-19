import api from '@/services/api'

/** Singleton Axios instance with JWT interceptor + auto-refresh. */
export function useApi() {
  return { api }
}
