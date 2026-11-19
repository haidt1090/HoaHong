<template>
  <div>
    <PageHeader title="Thêm công ty" />
    <CompanyForm
      :submitting="submitting"
      :error-msg="errorMsg"
      submit-label="Lưu"
      @submit="handleSubmit"
      @cancel="router.push({ name: 'company-list' })"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/common/PageHeader.vue'
import CompanyForm from '@/components/companies/CompanyForm.vue'
import { useCompanyStore } from '@/stores/companies'
import { useToast } from '@/composables/useToast'
import { extractError } from '@/services/api'
import type { CompanyInput } from '@/types'

const router = useRouter()
const store = useCompanyStore()
const toast = useToast()

const submitting = ref(false)
const errorMsg = ref('')

async function handleSubmit(payload: CompanyInput): Promise<void> {
  errorMsg.value = ''
  submitting.value = true
  try {
    const created = await store.create(payload)
    toast.showSuccess('Đã thêm công ty')
    router.push({ name: 'company-detail', params: { id: created.id } })
  } catch (err) {
    errorMsg.value = extractError(err, 'Lỗi khi lưu công ty')
  } finally {
    submitting.value = false
  }
}
</script>
