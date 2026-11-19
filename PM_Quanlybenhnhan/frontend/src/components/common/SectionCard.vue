<template>
  <section class="rounded-lg border border-gray-200 bg-white">
    <header
      v-if="title"
      class="flex items-center gap-2 px-5 py-3"
      :class="{ 'border-b border-gray-100': !collapsed }"
    >
      <i v-if="icon" :class="icon" class="text-primary" />
      <h3 class="m-0 text-base font-semibold text-text-body">{{ title }}</h3>
      <div class="ml-auto flex items-center gap-2">
        <slot name="actions" />
        <button
          v-if="collapsible"
          type="button"
          class="flex h-7 w-7 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-gray-100 hover:text-primary"
          :aria-label="collapsed ? 'Mở rộng' : 'Thu gọn'"
          @click="collapsed = !collapsed"
        >
          <i :class="collapsed ? 'pi pi-chevron-down' : 'pi pi-chevron-up'" />
        </button>
      </div>
    </header>
    <div v-show="!collapsed" class="p-5">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = withDefaults(
  defineProps<{
    title?: string
    icon?: string
    collapsible?: boolean
    defaultCollapsed?: boolean
  }>(),
  { title: '', icon: '', collapsible: false, defaultCollapsed: false },
)

const collapsed = ref(props.defaultCollapsed)
</script>
