<template>
  <div class="flex min-h-[60vh] flex-col items-center justify-center text-center">
    <h1 class="m-0 text-8xl font-bold text-danger">403</h1>
    <p class="mb-6 mt-2 text-lg text-text-muted">Bạn không có quyền truy cập trang này</p>
    <Button label="Về trang chủ" icon="pi pi-home" @click="router.push('/')" />
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
const router = useRouter()
</script>
