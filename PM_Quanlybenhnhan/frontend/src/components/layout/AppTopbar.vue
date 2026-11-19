<template>
  <header class="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4">
    <div class="flex items-center gap-3">
      <span
        class="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
        :class="isOnline ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger'"
      >
        <i :class="isOnline ? 'pi pi-wifi' : 'pi pi-ban'" class="text-xs" />
        {{ isOnline ? 'Trực tuyến' : 'Ngoại tuyến' }}
      </span>
    </div>

    <div class="flex items-center gap-2">
      <Button
        type="button"
        text
        severity="secondary"
        class="flex items-center gap-2"
        aria-haspopup="true"
        aria-controls="user-menu"
        @click="toggle"
      >
        <Avatar :label="initials" shape="circle" class="bg-primary text-white" size="normal" />
        <span class="hidden text-sm sm:inline">{{ displayName }}</span>
        <i class="pi pi-angle-down text-xs" />
      </Button>
      <Menu id="user-menu" ref="menu" :model="menuModel" :popup="true" />
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Avatar from 'primevue/avatar'
import Menu from 'primevue/menu'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const isOnline = ref(navigator.onLine)
function updateStatus(): void {
  isOnline.value = navigator.onLine
}
onMounted(() => {
  window.addEventListener('online', updateStatus)
  window.addEventListener('offline', updateStatus)
})
onUnmounted(() => {
  window.removeEventListener('online', updateStatus)
  window.removeEventListener('offline', updateStatus)
})

const displayName = computed(() => authStore.user?.full_name || authStore.user?.email || '')
const initials = computed(() => {
  const name = authStore.user?.full_name || authStore.user?.email || '?'
  return name.trim().charAt(0).toUpperCase()
})

const menu = ref<InstanceType<typeof Menu> | null>(null)
const menuModel = [
  {
    label: 'Đổi mật khẩu',
    icon: 'pi pi-key',
    command: () => router.push({ name: 'change-password' }),
  },
  {
    label: 'Đăng xuất',
    icon: 'pi pi-sign-out',
    command: async () => {
      await authStore.logout()
      router.push({ name: 'login' })
    },
  },
]

function toggle(event: Event): void {
  menu.value?.toggle(event)
}
</script>
