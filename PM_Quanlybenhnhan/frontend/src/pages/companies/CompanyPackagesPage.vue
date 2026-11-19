<template>
  <div>
    <PageHeader :title="`Gói khám — ${companyName}`" subtitle="Quản lý gói khám gán cho công ty">
      <template #actions>
        <Button label="Gán gói khám" icon="pi pi-plus" @click="openAssign" />
      </template>
    </PageHeader>

    <LoadingSkeleton v-if="packageStore.loading" type="card" :rows="3" />
    <PackageList v-else :packages="packages" @edit="openEdit" @deactivate="handleDeactivate" />

    <PackageAssignmentModal
      v-model:visible="modalVisible"
      :available-packages="packageStore.examPackages"
      :editing-package="editingPackage"
      :saving="saving"
      :error-msg="modalError"
      @save="handleSave"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Button from 'primevue/button'
import PageHeader from '@/components/common/PageHeader.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import PackageList from '@/components/packages/PackageList.vue'
import PackageAssignmentModal from '@/components/packages/PackageAssignmentModal.vue'
import { usePackageStore } from '@/stores/packages'
import { useCompanyStore } from '@/stores/companies'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { extractError } from '@/services/api'
import type { CompanyExamPackage, CompanyExamPackageInput } from '@/types'

const route = useRoute()
const companyId = route.params.id as string
const packageStore = usePackageStore()
const companyStore = useCompanyStore()
const toast = useToast()
const confirm = useConfirm()

const modalVisible = ref(false)
const editingPackage = ref<CompanyExamPackage | null>(null)
const saving = ref(false)
const modalError = ref('')

const packages = computed(() => packageStore.companyPackages[companyId] ?? [])
const companyName = computed(() => companyStore.current?.name ?? 'Công ty')

function openAssign(): void {
  editingPackage.value = null
  modalError.value = ''
  modalVisible.value = true
}

function openEdit(pkg: CompanyExamPackage): void {
  editingPackage.value = pkg
  modalError.value = ''
  modalVisible.value = true
}

async function handleSave(payload: CompanyExamPackageInput): Promise<void> {
  if (!payload.exam_package) {
    modalError.value = 'Vui lòng chọn gói khám'
    return
  }
  modalError.value = ''
  saving.value = true
  try {
    if (editingPackage.value) {
      await packageStore.updatePackage(companyId, editingPackage.value.id, payload)
      toast.showSuccess('Đã cập nhật gói khám')
    } else {
      await packageStore.assignPackage(companyId, payload)
      toast.showSuccess('Đã gán gói khám')
    }
    modalVisible.value = false
  } catch (err) {
    modalError.value = extractError(err, 'Lỗi khi lưu gói khám')
  } finally {
    saving.value = false
  }
}

async function handleDeactivate(pkg: CompanyExamPackage): Promise<void> {
  const ok = await confirm.require('Ngừng gói khám', 'Ngừng áp dụng gói khám này?', true)
  if (!ok) return
  try {
    await packageStore.deactivatePackage(companyId, pkg.id)
    toast.showSuccess('Đã ngừng gói khám')
  } catch (err) {
    toast.showError(extractError(err, 'Không thể ngừng gói khám'))
  }
}

onMounted(async () => {
  await Promise.all([
    companyStore.fetchById(companyId),
    packageStore.fetchCompanyPackages(companyId),
    packageStore.fetchExamPackages(),
  ])
})
</script>
