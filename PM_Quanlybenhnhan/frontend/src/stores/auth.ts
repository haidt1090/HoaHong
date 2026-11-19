import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authService } from '@/services/auth'
import type { Role, User } from '@/types'

const ROLE_HIERARCHY: Record<Role, number> = {
  admin: 6,
  doctor: 5,
  nurse: 4,
  labtech: 3,
  company_admin: 2,
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const accessToken = ref<string | null>(localStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => !!user.value)
  const mustChangePassword = computed(() => user.value?.must_change_password ?? false)

  function hasRole(minRole: Role): boolean {
    if (!user.value) return false
    return ROLE_HIERARCHY[user.value.role] >= ROLE_HIERARCHY[minRole]
  }

  function isRole(...roles: Role[]): boolean {
    return !!user.value && roles.includes(user.value.role)
  }

  function setTokens(access: string, refresh: string): void {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem('access_token', access)
    localStorage.setItem('refresh_token', refresh)
  }

  function clearTokens(): void {
    accessToken.value = null
    refreshToken.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  async function login(email: string, password: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const { data } = await authService.login(email, password)
      setTokens(data.access, data.refresh)
      user.value = data.user
    } finally {
      loading.value = false
    }
  }

  async function fetchMe(): Promise<void> {
    try {
      const { data } = await authService.me()
      user.value = data
    } catch {
      user.value = null
    }
  }

  async function logout(): Promise<void> {
    try {
      await authService.logout(refreshToken.value)
    } catch {
      // ignore network/blacklist failures on logout
    }
    user.value = null
    clearTokens()
  }

  async function changePassword(payload: {
    old_password: string
    new_password: string
  }): Promise<void> {
    await authService.changePassword(payload)
    if (user.value) user.value.must_change_password = false
  }

  async function init(): Promise<void> {
    if (accessToken.value && !user.value) {
      await fetchMe()
    }
  }

  return {
    user,
    accessToken,
    refreshToken,
    loading,
    error,
    isAuthenticated,
    mustChangePassword,
    hasRole,
    isRole,
    login,
    logout,
    fetchMe,
    changePassword,
    init,
  }
})
