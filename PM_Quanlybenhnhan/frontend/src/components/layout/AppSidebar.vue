<template>
  <aside
    class="flex flex-col border-r border-gray-200 bg-white transition-all duration-200"
    :class="collapsed ? 'w-16' : 'w-60'"
  >
    <div class="flex h-14 items-center gap-2 border-b border-gray-100 px-4">
      <i class="pi pi-heart-fill text-xl text-primary" />
      <span v-if="!collapsed" class="truncate text-sm font-bold text-primary">
        Y Cao Hoa Hồng
      </span>
    </div>

    <nav class="flex-1 overflow-y-auto py-3">
      <router-link
        v-for="item in menuItems"
        :key="item.to"
        :to="item.to"
        class="mx-2 mb-1 flex items-center gap-3 rounded-md px-3 py-2.5 text-sm text-text-body transition-colors hover:bg-primary/10"
        :active-class="item.exact ? '' : 'bg-primary/15 font-semibold text-primary'"
        exact-active-class="bg-primary/15 font-semibold text-primary"
        :title="collapsed ? item.label : undefined"
      >
        <i :class="item.icon" class="text-lg" />
        <span v-if="!collapsed">{{ item.label }}</span>
      </router-link>
    </nav>

    <button
      class="flex items-center justify-center border-t border-gray-100 py-3 text-text-muted hover:text-primary"
      :aria-label="collapsed ? 'Mở rộng' : 'Thu gọn'"
      @click="$emit('update:collapsed', !collapsed)"
    >
      <i :class="collapsed ? 'pi pi-angle-right' : 'pi pi-angle-left'" />
    </button>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import type { Role, MenuItemDef } from '@/types'

defineProps<{ collapsed: boolean }>()
defineEmits<{ 'update:collapsed': [value: boolean] }>()

const authStore = useAuthStore()

const MENU_BY_ROLE: Record<Role, MenuItemDef[]> = {
  admin: [
    { label: 'Tổng quan', icon: 'pi pi-home', to: '/' },
    { label: 'Bệnh nhân', icon: 'pi pi-users', to: '/patients', visible: false },
    { label: 'Công ty', icon: 'pi pi-building', to: '/companies' },
    { label: 'Khám bệnh', icon: 'pi pi-file-edit', to: '/examinations', visible: true },
    { label: 'Chẩn đoán', icon: 'pi pi-lightbulb', to: '/diagnosis/keywords' },
    { label: 'Báo cáo', icon: 'pi pi-chart-bar', to: '/reports' },
    { label: 'Nhập/Xuất', icon: 'pi pi-upload', to: '/import' },
    { label: 'Đồng bộ CSDLKSK', icon: 'pi pi-cloud-upload', to: '/sync', exact: true },
    { label: 'Ký USB', icon: 'pi pi-key', to: '/sync/usb-signer' },
    { label: 'Mapping XML', icon: 'pi pi-link', to: '/sync/mapping' },
    { label: 'Chữ ký số', icon: 'pi pi-pencil', to: '/sync/signatures' },
  ],
  doctor: [
    { label: 'Tổng quan', icon: 'pi pi-home', to: '/' },
    { label: 'Bệnh nhân', icon: 'pi pi-users', to: '/patients', visible: false },
    { label: 'Công ty', icon: 'pi pi-building', to: '/companies' },
    { label: 'Khám bệnh', icon: 'pi pi-file-edit', to: '/examinations', visible: true },
    { label: 'Báo cáo', icon: 'pi pi-chart-bar', to: '/reports' },
    { label: 'Nhập/Xuất', icon: 'pi pi-upload', to: '/import' },
    { label: 'Ký USB', icon: 'pi pi-key', to: '/sync/usb-signer' },
  ],
  nurse: [
    { label: 'Tổng quan', icon: 'pi pi-home', to: '/' },
    { label: 'Bệnh nhân', icon: 'pi pi-users', to: '/patients', visible: false },
    { label: 'Khám bệnh', icon: 'pi pi-file-edit', to: '/examinations', visible: false },
    { label: 'Nhập/Xuất', icon: 'pi pi-upload', to: '/import' },
  ],
  labtech: [
    { label: 'Tổng quan', icon: 'pi pi-home', to: '/' },
    { label: 'Bệnh nhân', icon: 'pi pi-users', to: '/patients', visible: false },
    { label: 'Khám bệnh', icon: 'pi pi-file-edit', to: '/examinations', visible: false },
    { label: 'Nhập/Xuất', icon: 'pi pi-upload', to: '/import' },
  ],
  company_admin: [
    { label: 'Tổng quan', icon: 'pi pi-home', to: '/' },
    { label: 'Bệnh nhân', icon: 'pi pi-users', to: '/patients' },
  ],
}

const menuItems = computed<MenuItemDef[]>(() => {
  const role = authStore.user?.role
  return role ? MENU_BY_ROLE[role].filter((item) => item.visible !== false) : []
})
</script>
