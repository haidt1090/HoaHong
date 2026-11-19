<template>
  <div>
    <PageHeader
      :title="`Xin chào, ${displayName}`"
      subtitle="Chào mừng đến với hệ thống quản lý khám sức khỏe"
    />

    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <SectionCard v-for="stat in stats" :key="stat.label">
        <div class="flex items-center gap-4">
          <div class="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
            <i :class="stat.icon" class="text-xl text-primary" />
          </div>
          <div>
            <div class="text-2xl font-bold text-text-body">{{ stat.value }}</div>
            <div class="text-sm text-text-muted">{{ stat.label }}</div>
          </div>
        </div>
      </SectionCard>
    </div>

    <SectionCard title="Thao tác nhanh" icon="pi pi-bolt" class="mt-6">
      <div class="flex flex-wrap gap-3">
        <Button
          label="Thêm bệnh nhân"
          icon="pi pi-user-plus"
          outlined
          @click="router.push({ name: 'patient-create' })"
        />
        <Button
          label="Danh sách bệnh nhân"
          icon="pi pi-users"
          outlined
          @click="router.push({ name: 'patient-list' })"
        />
        <Button
          v-if="authStore.isRole('admin', 'doctor')"
          label="Quản lý công ty"
          icon="pi pi-building"
          outlined
          @click="router.push({ name: 'company-list' })"
        />
      </div>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const displayName = computed(() => authStore.user?.full_name || authStore.user?.email || '')

const stats = [
  { label: 'Bệnh nhân hôm nay', value: '--', icon: 'pi pi-user' },
  { label: 'Phiếu khám hôm nay', value: '--', icon: 'pi pi-file' },
  { label: 'Tổng bệnh nhân', value: '--', icon: 'pi pi-users' },
  { label: 'Tổng công ty', value: '--', icon: 'pi pi-building' },
]
</script>
