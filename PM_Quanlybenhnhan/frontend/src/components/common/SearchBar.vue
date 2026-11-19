<template>
  <IconField class="w-full sm:w-80">
    <InputIcon class="pi pi-search" />
    <InputText
      :model-value="modelValue"
      :placeholder="placeholder"
      class="w-full"
      @update:model-value="onInput"
    />
  </IconField>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import InputText from 'primevue/inputtext'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'

const props = withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    delay?: number
  }>(),
  { placeholder: 'Tìm kiếm...', delay: 300 },
)

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

let timer: ReturnType<typeof setTimeout> | undefined
const pending = ref(props.modelValue)

function onInput(value: string | undefined): void {
  pending.value = value ?? ''
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => emit('update:modelValue', pending.value), props.delay)
}
</script>
