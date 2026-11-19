<template>
  <Dialog
    :visible="visible"
    header="Phím tắt"
    :style="{ width: '520px' }"
    modal
    @update:visible="$emit('update:visible', $event)"
  >
    <div v-for="group in groups" :key="group.group" class="mb-5 last:mb-0">
      <h4 class="mb-2 text-sm font-semibold text-text-body">{{ group.group }}</h4>
      <ul class="space-y-2">
        <li
          v-for="s in enabledShortcuts(group)"
          :key="s.id"
          class="flex items-center justify-between gap-4 rounded-md px-2 py-1 hover:bg-gray-50"
        >
          <div class="text-sm text-text-body">
            <div>{{ s.label }}</div>
            <div v-if="s.description" class="text-xs text-text-muted">{{ s.description }}</div>
          </div>
          <span class="flex shrink-0 items-center gap-1">
            <kbd
              v-for="key in splitCombo(s.combo)"
              :key="key"
              class="rounded border border-gray-300 bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-text-body"
            >
              {{ key }}
            </kbd>
          </span>
        </li>
      </ul>
    </div>

    <template #footer>
      <Button label="Đóng" severity="secondary" @click="$emit('update:visible', false)" />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import type { ShortcutDefinition, ShortcutGroup } from '@/shortcuts'

defineProps<{ visible: boolean; groups: ShortcutGroup[] }>()
defineEmits<{ 'update:visible': [value: boolean] }>()

function enabledShortcuts(group: ShortcutGroup): ShortcutDefinition[] {
  return group.shortcuts.filter((s) => s.enabled)
}

/** Splits a combo like `Ctrl+Shift+S` or `Ctrl+1 … Ctrl+9` into display parts. */
function splitCombo(combo: string): string[] {
  if (combo.includes('…')) {
    return combo
      .split('…')
      .map((p) => p.trim())
      .filter(Boolean)
  }
  return combo
    .split('+')
    .map((p) => p.trim())
    .filter(Boolean)
}
</script>
