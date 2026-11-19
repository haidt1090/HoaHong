<template>
  <div>
    <Button
      icon="pi pi-ellipsis-v"
      text
      rounded
      severity="secondary"
      aria-label="Thao tác"
      @click="toggle"
    />
    <Menu ref="menu" :model="menuModel" :popup="true" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import Button from 'primevue/button'
import Menu from 'primevue/menu'
import type { ActionDef } from '@/types'

const props = defineProps<{ actions: ActionDef[] }>()

const menu = ref<InstanceType<typeof Menu> | null>(null)

const menuModel = computed(() =>
  props.actions.map((action) => ({
    label: action.label,
    icon: action.icon,
    disabled: action.disabled,
    command: action.handler,
  })),
)

function toggle(event: Event): void {
  menu.value?.toggle(event)
}
</script>
