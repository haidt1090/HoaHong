import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

interface QueueItem {
  resolve: (token: string) => void
  reject: (error: unknown) => void
}

let isRefreshing = false
let failedQueue: QueueItem[] = []

function processQueue(error: unknown, token: string | null = null): void {
  failedQueue.forEach((item) => {
    if (error || !token) {
      item.reject(error)
    } else {
      item.resolve(token)
    }
  })
  failedQueue = []
}

function redirectToLogin(): void {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  if (!window.location.pathname.endsWith('/login')) {
    window.location.href = '/khamsk/login'
  }
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as
      (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return api(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        redirectToLogin()
        return Promise.reject(error)
      }

      try {
        const { data } = await axios.post<{ access: string }>(`${BASE_URL}/auth/refresh/`, {
          refresh: refreshToken,
        })
        localStorage.setItem('access_token', data.access)
        processQueue(null, data.access)
        originalRequest.headers.Authorization = `Bearer ${data.access}`
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        redirectToLogin()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  },
)

function parseIfJson(value: string): string {
  if (typeof value !== 'string' || !value.trimStart().startsWith('{')) return value
  try {
    const parsed = JSON.parse(value)
    if (parsed && typeof parsed === 'object') {
      if (typeof parsed.detail === 'string') return parsed.detail
      if (typeof parsed.message === 'string') return parsed.message
    }
    return value
  } catch {
    return value
  }
}

function stringifyDetail(value: unknown): string {
  if (typeof value === 'string') return parseIfJson(value)
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>
    // Handle DRF standard format: {"detail": "..."}
    if (typeof obj.detail === 'string') return obj.detail
    // Handle custom exception handler wrap: {"error": {"detail": "..."}}
    if (obj.error && typeof obj.error === 'object') return stringifyDetail(obj.error)
    // Handle nested message field
    if (typeof obj.message === 'string') return obj.message
    // Collect field-level validation errors
    const parts: string[] = []
    for (const [key, val] of Object.entries(obj)) {
      if (key === 'code' || key === 'fields' || key === 'error') continue
      if (Array.isArray(val)) {
        for (const item of val) parts.push(typeof item === 'string' ? item : String(item))
      } else if (typeof val === 'string') {
        parts.push(val)
      } else if (val && typeof val === 'object') {
        const nested = stringifyDetail(val)
        if (nested) parts.push(nested)
      }
    }
    return parts.length ? parts.join(', ') : ''
  }
  return ''
}

/** Extract a human-readable message from a DRF error response. */
export function extractError(err: unknown, fallback = 'Đã có lỗi xảy ra'): string {
  const axiosErr = err as AxiosError<Record<string, unknown>>
  const data = axiosErr.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return parseIfJson(data)
  return stringifyDetail(data) || fallback
}

export default api
