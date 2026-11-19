<template>
  <div
    class="flex min-h-screen items-center justify-center bg-gradient-to-br from-primary to-primary-dark p-4"
  >
    <div class="w-full max-w-md rounded-xl bg-white p-8 shadow-2xl">
      <div class="mb-8 text-center">
        <i class="pi pi-heart-fill text-4xl text-primary" />
        <h1 class="mt-3 text-xl font-bold text-text-body">PKĐK Y Cao Hoa Hồng</h1>
        <p class="mt-1 text-sm text-text-muted">Hệ thống quản lý khám sức khỏe</p>
      </div>

      <form class="flex flex-col gap-5" @submit.prevent="handleLogin">
        <Message v-if="errorMsg" severity="error" :closable="false">{{ errorMsg }}</Message>

        <FormField label="Email" required>
          <InputText
            v-model="email"
            type="email"
            placeholder="Nhập email"
            autocomplete="username"
            class="w-full"
            required
          />
        </FormField>

        <FormField label="Mật khẩu" required>
          <Password
            v-model="password"
            placeholder="Nhập mật khẩu"
            :feedback="false"
            toggle-mask
            input-class="w-full"
            class="w-full"
            fluid
            required
          />
        </FormField>

        <Button type="submit" label="Đăng nhập" :loading="authStore.loading" class="w-full" />
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import FormField from '@/components/common/FormField.vue'
import { useAuthStore } from '@/stores/auth'
import { extractError } from '@/services/api'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const email = ref('')
const password = ref('')
const errorMsg = ref('')

async function handleLogin(): Promise<void> {
  errorMsg.value = ''
  try {
    await authStore.login(email.value, password.value)
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (err) {
    errorMsg.value = extractError(err, 'Email hoặc mật khẩu không đúng')
  }
}
</script>
