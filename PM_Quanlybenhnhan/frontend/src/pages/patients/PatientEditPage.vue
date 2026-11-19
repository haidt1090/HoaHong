<template>
  <div>
    <PageHeader title="Sửa thông tin bệnh nhân" />
    <LoadingSkeleton v-if="loading" type="form" :rows="6" />
    <PatientForm
      v-else
      :model-value="store.current"
      :companies="companyStore.list"
      :submitting="submitting"
      :error-msg="errorMsg"
      submit-label="Lưu thay đổi"
      @submit="handleSubmit"
      @cancel="router.push({ name: 'patient-detail', params: { id: route.params.id as string } })"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import PageHeader from '@/components/common/PageHeader.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import PatientForm from '@/components/patients/PatientForm.vue'
import { usePatientStore } from '@/stores/patients'
import { useCompanyStore } from '@/stores/companies'
import { useToast } from '@/composables/useToast'
import { extractError } from '@/services/api'
import type { PatientInput } from '@/types'

const router = useRouter()
const route = useRoute()
const store = usePatientStore()
const companyStore = useCompanyStore()
const toast = useToast()

const loading = ref(true)
const submitting = ref(false)
const errorMsg = ref('')

async function handleSubmit(payload: PatientInput): Promise<void> {
  errorMsg.value = ''
  submitting.value = true
  try {
    await store.update(route.params.id as string, payload)
    toast.showSuccess('Đã cập nhật bệnh nhân')
    router.push({ name: 'patient-detail', params: { id: route.params.id as string } })
  } catch (err) {
    errorMsg.value = extractError(err, 'Lỗi khi lưu')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  companyStore.filters.page_size = 200
  await Promise.all([store.fetchById(route.params.id as string), companyStore.fetchList()])
  loading.value = false
})
</script>
