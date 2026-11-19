<template>
  <div class="flex h-screen overflow-hidden">
    <AppSidebar v-model:collapsed="collapsed" />
    <div class="flex flex-1 flex-col overflow-hidden">
      <AppTopbar />
      <main class="flex-1 overflow-y-auto bg-bg-page p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AppSidebar from './AppSidebar.vue'
import AppTopbar from './AppTopbar.vue'

const collapsed = ref(false)
</script>
