<template>
  <div>
    <PageHeader title="Sửa thông tin công ty" />
    <LoadingSkeleton v-if="loading" type="form" :rows="5" />
    <CompanyForm
      v-else
      :model-value="store.current"
      :submitting="submitting"
      :error-msg="errorMsg"
      submit-label="Lưu thay đổi"
      @submit="handleSubmit"
      @cancel="router.push({ name: 'company-detail', params: { id: route.params.id as string } })"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import PageHeader from '@/components/common/PageHeader.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import CompanyForm from '@/components/companies/CompanyForm.vue'
import { useCompanyStore } from '@/stores/companies'
import { useToast } from '@/composables/useToast'
import { extractError } from '@/services/api'
import type { CompanyInput } from '@/types'

const router = useRouter()
const route = useRoute()
const store = useCompanyStore()
const toast = useToast()

const loading = ref(true)
const submitting = ref(false)
const errorMsg = ref('')

async function handleSubmit(payload: CompanyInput): Promise<void> {
  errorMsg.value = ''
  submitting.value = true
  try {
    await store.update(route.params.id as string, payload)
    toast.showSuccess('Đã cập nhật công ty')
    router.push({ name: 'company-detail', params: { id: route.params.id as string } })
  } catch (err) {
    errorMsg.value = extractError(err, 'Lỗi khi lưu')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await store.fetchById(route.params.id as string)
  loading.value = false
})
</script>
