<template>
  <form class="flex flex-col gap-6" @submit.prevent="onSubmit">
    <Message v-if="errorMsg" severity="error" :closable="false">{{ errorMsg }}</Message>

    <SectionCard title="Thông tin công ty" icon="pi pi-building">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField label="Tên công ty" required :error="errors.name">
          <InputText v-model="form.name" class="w-full" placeholder="Công ty TNHH ABC" />
        </FormField>
        <FormField label="Mã công ty" help-text="Dùng cho cổng tra cứu kết quả">
          <InputText v-model="form.code" class="w-full" />
        </FormField>
        <FormField label="Mã số thuế">
          <InputText v-model="form.tax_code" class="w-full" />
        </FormField>
        <FormField label="Địa chỉ" class="md:col-span-2">
          <InputText v-model="form.address" class="w-full" />
        </FormField>
      </div>
    </SectionCard>

    <SectionCard title="Người liên hệ" icon="pi pi-user">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <FormField label="Người liên hệ">
          <InputText v-model="form.contact_person" class="w-full" />
        </FormField>
        <FormField label="Điện thoại">
          <InputText v-model="form.contact_phone" class="w-full" />
        </FormField>
        <FormField label="Email" :error="errors.contact_email">
          <InputText v-model="form.contact_email" type="email" class="w-full" />
        </FormField>
      </div>
      <div class="mt-4 flex items-center gap-3">
        <ToggleSwitch v-model="form.is_active" input-id="company-active" />
        <label for="company-active" class="cursor-pointer text-sm font-medium"
          >Đang hoạt động</label
        >
      </div>
    </SectionCard>

    <div class="flex justify-end gap-2">
      <Button type="button" label="Hủy" severity="secondary" @click="$emit('cancel')" />
      <Button type="submit" :label="submitLabel ?? 'Lưu'" :loading="submitting" />
    </div>
  </form>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import InputText from 'primevue/inputtext'
import ToggleSwitch from 'primevue/toggleswitch'
import Button from 'primevue/button'
import Message from 'primevue/message'
import FormField from '@/components/common/FormField.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import type { Company, CompanyInput } from '@/types'

const props = defineProps<{
  modelValue?: Company | null
  submitting?: boolean
  submitLabel?: string
  errorMsg?: string
}>()

const emit = defineEmits<{
  submit: [payload: CompanyInput]
  cancel: []
}>()

const errors = reactive<Record<string, string>>({})

const form = reactive<CompanyInput>({
  name: '',
  code: '',
  address: '',
  tax_code: '',
  contact_person: '',
  contact_phone: '',
  contact_email: '',
  is_active: true,
})

watch(
  () => props.modelValue,
  (company) => {
    if (!company) return
    Object.assign(form, {
      name: company.name,
      code: company.code,
      address: company.address,
      tax_code: company.tax_code,
      contact_person: company.contact_person,
      contact_phone: company.contact_phone,
      contact_email: company.contact_email,
      is_active: company.is_active,
    })
  },
  { immediate: true },
)

function validate(): boolean {
  Object.keys(errors).forEach((k) => delete errors[k])
  if (!form.name) errors.name = 'Vui lòng nhập tên công ty'
  if (form.contact_email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.contact_email)) {
    errors.contact_email = 'Email không hợp lệ'
  }
  return Object.keys(errors).length === 0
}

function onSubmit(): void {
  if (!validate()) return
  emit('submit', { ...form })
}
</script>
