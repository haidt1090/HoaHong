<template>
  <div>
    <LoadingSkeleton v-if="loading" type="form" :rows="5" />
    <template v-else-if="company">
      <PageHeader :title="company.name">
        <template #actions>
          <StatusBadge :status="company.is_active ? 'active' : 'inactive'" />
          <Button
            v-if="isRole('admin')"
            label="Gói khám"
            icon="pi pi-box"
            outlined
            @click="router.push({ name: 'company-packages', params: { id: company.id } })"
          />
          <Button
            v-if="isRole('admin')"
            label="Sửa"
            icon="pi pi-pencil"
            outlined
            @click="router.push({ name: 'company-edit', params: { id: company.id } })"
          />
          <Button
            v-if="isRole('admin')"
            label="Xóa"
            icon="pi pi-trash"
            severity="danger"
            outlined
            @click="handleDelete"
          />
        </template>
      </PageHeader>

      <Tabs v-model:value="activeTab">
        <TabList>
          <Tab value="info">Thông tin</Tab>
          <Tab value="employees">Nhân viên</Tab>
          <Tab value="data-entry">Nhập liệu</Tab>
        </TabList>
        <TabPanels>
          <TabPanel value="info">
            <SectionCard>
              <dl class="m-0">
                <InfoRow label="Tên công ty" :value="company.name" />
                <InfoRow label="Mã công ty" :value="company.code" />
                <InfoRow label="Mã số thuế" :value="company.tax_code" />
                <InfoRow label="Địa chỉ" :value="company.address" />
                <InfoRow label="Người liên hệ" :value="company.contact_person" />
                <InfoRow label="Điện thoại" :value="company.contact_phone" />
                <InfoRow label="Email" :value="company.contact_email" />
              </dl>
            </SectionCard>
          </TabPanel>
          <TabPanel value="employees">
            <SectionCard>
              <EmployeeListTab :company-id="company.id" :active="activeTab === 'employees'" @start-entry="onStartEntry" />
            </SectionCard>
          </TabPanel>
          <TabPanel value="data-entry">
            <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div>
                <h4 class="mb-2 text-sm font-semibold text-text-body">Tìm nhân viên</h4>
                <EmployeeSearchPanel ref="employeeSearchPanel" :company-id="company.id" :pre-selected-id="selectedEmployeeId" @select="onEmployeeSelect" />
              </div>
              <div>
                <h4 class="mb-2 text-sm font-semibold text-text-body">Chọn gói khám</h4>
                <PackageSelector
                  :company-id="company.id"
                  :model-value="selectedPackages"
                  @update:model-value="selectedPackages = $event"
                />
              </div>
            </div>
            <SectionCard class="mt-4">
              <DataEntryPanel
                :company-id="company.id"
                :employee-id="selectedEmployeeId"
                :package-ids="selectedPackages"
                :active="activeTab === 'data-entry'"
                @saved="onDataEntrySaved"
                @select-employee="onEmployeeSelect"
                @focus-search="focusEmployeeSearch"
              />
            </SectionCard>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Button from 'primevue/button'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import InfoRow from '@/components/common/InfoRow.vue'
import EmployeeListTab from '@/components/companies/EmployeeListTab.vue'
import EmployeeSearchPanel from '@/components/companies/EmployeeSearchPanel.vue'
import PackageSelector from '@/components/companies/PackageSelector.vue'
import DataEntryPanel from '@/components/companies/DataEntryPanel.vue'
import { useCompanyStore } from '@/stores/companies'
import { useAuth } from '@/composables/useAuth'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { extractError } from '@/services/api'
import { packagesService } from '@/services/packages'
import type { Patient, CompanyExamPackage } from '@/types'

const router = useRouter()
const route = useRoute()
const store = useCompanyStore()
const { isRole } = useAuth()
const toast = useToast()
const confirm = useConfirm()

const loading = ref(true)
const activeTab = ref('info')
const company = computed(() => store.current)
const selectedEmployeeId = ref<string | null>(null)
const selectedPackages = ref<string[]>([])
const employeeSearchPanel = ref<{ focusSearch: () => void } | null>(null)

async function handleDelete(): Promise<void> {
  const ok = await confirm.require('Xóa công ty', 'Bạn có chắc muốn xóa công ty này?', true)
  if (!ok) return
  try {
    await store.remove(route.params.id as string)
    toast.showSuccess('Đã xóa công ty')
    router.push({ name: 'company-list' })
  } catch (err) {
    toast.showError(extractError(err, 'Không thể xóa công ty'))
  }
}

function onEmployeeSelect(patient: Patient): void {
  selectedEmployeeId.value = patient.id
}

function focusEmployeeSearch(): void {
  nextTick(() => employeeSearchPanel.value?.focusSearch())
}

function onStartEntry(patient: Patient): void {
  selectedEmployeeId.value = patient.id
  activeTab.value = 'data-entry'
}

function onDataEntrySaved(): void {
  // data entry saved successfully
}

onMounted(async () => {
  await store.fetchById(route.params.id as string)
  loading.value = false
})

watch(activeTab, async (tab) => {
  if (tab === 'data-entry' && selectedPackages.value.length === 0 && company.value) {
    try {
      const { data: cpData } = await packagesService.listCompanyPackages(company.value.id)
      const pkgs: CompanyExamPackage[] = Array.isArray(cpData)
        ? cpData as CompanyExamPackage[]
        : (cpData as { results?: CompanyExamPackage[] }).results ?? []
      const active = pkgs.filter((p) => p.is_active)
      if (active.length > 0) {
        selectedPackages.value = [active[0].id]
      }
    } catch {
      // ignore
    }
  }
})
</script>
