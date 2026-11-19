<template>
  <div>
    <PageHeader title="Thêm bệnh nhân" />
    <PatientForm
      :companies="companyStore.list"
      :submitting="submitting"
      :error-msg="errorMsg"
      submit-label="Lưu"
      @submit="handleSubmit"
      @cancel="router.push({ name: 'patient-list' })"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/common/PageHeader.vue'
import PatientForm from '@/components/patients/PatientForm.vue'
import { usePatientStore } from '@/stores/patients'
import { useCompanyStore } from '@/stores/companies'
import { useToast } from '@/composables/useToast'
import { extractError } from '@/services/api'
import type { PatientInput } from '@/types'

const router = useRouter()
const store = usePatientStore()
const companyStore = useCompanyStore()
const toast = useToast()

const submitting = ref(false)
const errorMsg = ref('')

async function handleSubmit(payload: PatientInput): Promise<void> {
  errorMsg.value = ''
  submitting.value = true
  try {
    const created = await store.create(payload)
    toast.showSuccess('Đã thêm bệnh nhân')
    router.push({ name: 'patient-detail', params: { id: created.id } })
  } catch (err) {
    errorMsg.value = extractError(err, 'Lỗi khi lưu bệnh nhân')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  companyStore.filters.page_size = 200
  companyStore.fetchList()
})
</script>
