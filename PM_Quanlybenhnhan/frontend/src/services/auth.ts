import api from './api'
import type { User, LoginResponse } from '@/types'

export const authService = {
  login(email: string, password: string) {
    return api.post<LoginResponse>('/auth/login/', { email, password })
  },
  logout(refresh: string | null) {
    return api.post('/auth/logout/', refresh ? { refresh } : {})
  },
  refresh(refresh: string) {
    return api.post<{ access: string }>('/auth/refresh/', { refresh })
  },
  me() {
    return api.get<User>('/auth/me/')
  },
  updateProfile(payload: Partial<Pick<User, 'full_name' | 'phone'>>) {
    return api.put<User>('/auth/me/', payload)
  },
  changePassword(payload: { old_password: string; new_password: string }) {
    return api.post('/auth/change-password/', payload)
  },
}
