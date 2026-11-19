import { nextTick } from 'vue'

/**
 * Commit values that PrimeVue only writes on blur (notably InputNumber).
 *
 * InputNumber does not emit `update:modelValue` while focused — only on blur,
 * Enter, or spinner clicks. Ctrl+S / click-Save while the caret is still in a
 * number cell would otherwise PUT the previous (seeded or empty) payload and
 * the API would still return 200.
 */
export async function flushPendingInputs(): Promise<void> {
  const active = document.activeElement
  if (active instanceof HTMLElement) {
    active.blur()
  }
  await nextTick()
}
