import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import type { Role } from '@/types'

/**
 * Role guard composable. `allowed` is true when the current user's role is in
 * `requiredRoles` (or when no roles are required).
 */
export function useRoleGuard(requiredRoles?: Role[]) {
  const store = useAuthStore()

  const allowed = computed(() => {
    if (!requiredRoles || requiredRoles.length === 0) return store.isAuthenticated
    return store.isRole(...requiredRoles)
  })

  return { allowed }
}
