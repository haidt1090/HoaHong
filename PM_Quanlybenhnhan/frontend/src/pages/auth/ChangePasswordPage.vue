<template>
  <div class="flex min-h-screen items-center justify-center bg-bg-page p-4">
    <div class="w-full max-w-md rounded-xl bg-white p-8 shadow-lg">
      <h2 class="m-0 mb-2 text-xl font-bold text-text-body">Đổi mật khẩu</h2>
      <p v-if="authStore.mustChangePassword" class="mb-5 text-sm text-warning">
        Bạn cần đổi mật khẩu trước khi tiếp tục sử dụng hệ thống.
      </p>

      <form class="flex flex-col gap-4" @submit.prevent="handleSubmit">
        <Message v-if="errorMsg" severity="error" :closable="false">{{ errorMsg }}</Message>
        <Message v-if="successMsg" severity="success" :closable="false">{{ successMsg }}</Message>

        <FormField label="Mật khẩu hiện tại" required>
          <Password v-model="form.old_password" :feedback="false" toggle-mask fluid required />
        </FormField>
        <FormField label="Mật khẩu mới" required help-text="Ít nhất 8 ký tự">
          <Password v-model="form.new_password" toggle-mask fluid required />
        </FormField>
        <FormField
          label="Xác nhận mật khẩu mới"
          required
          :error="mismatch ? 'Mật khẩu không khớp' : ''"
        >
          <Password v-model="form.confirm_password" :feedback="false" toggle-mask fluid required />
        </FormField>

        <div class="flex gap-2">
          <Button type="submit" label="Đổi mật khẩu" :loading="submitting" />
          <Button
            v-if="!authStore.mustChangePassword"
            type="button"
            label="Hủy"
            severity="secondary"
            @click="router.back()"
          />
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import FormField from '@/components/common/FormField.vue'
import { useAuthStore } from '@/stores/auth'
import { extractError } from '@/services/api'

const authStore = useAuthStore()
const router = useRouter()

const submitting = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

const form = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const mismatch = computed(
  () => form.confirm_password.length > 0 && form.new_password !== form.confirm_password,
)

async function handleSubmit(): Promise<void> {
  errorMsg.value = ''
  successMsg.value = ''

  if (form.new_password !== form.confirm_password) {
    errorMsg.value = 'Mật khẩu mới không khớp'
    return
  }
  if (form.new_password.length < 8) {
    errorMsg.value = 'Mật khẩu phải có ít nhất 8 ký tự'
    return
  }

  submitting.value = true
  try {
    await authStore.changePassword({
      old_password: form.old_password,
      new_password: form.new_password,
    })
    successMsg.value = 'Đổi mật khẩu thành công'
    setTimeout(() => router.push({ name: 'dashboard' }), 1200)
  } catch (err) {
    errorMsg.value = extractError(err, 'Đổi mật khẩu thất bại')
  } finally {
    submitting.value = false
  }
}
</script>
