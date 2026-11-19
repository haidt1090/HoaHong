import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'

/**
 * Auth composable — thin wrapper over the auth store exposing reactive user
 * state and role helpers for components.
 */
export function useAuth() {
  const store = useAuthStore()
  const { user, isAuthenticated, mustChangePassword, loading } = storeToRefs(store)

  return {
    user,
    isAuthenticated,
    mustChangePassword,
    loading,
    login: store.login,
    logout: store.logout,
    fetchMe: store.fetchMe,
    changePassword: store.changePassword,
    hasRole: store.hasRole,
    isRole: store.isRole,
  }
}
