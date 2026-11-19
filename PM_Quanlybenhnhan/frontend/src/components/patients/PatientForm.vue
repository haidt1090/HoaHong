<template>
  <form class="flex flex-col gap-6" @submit.prevent="onSubmit">
    <Message v-if="errorMsg" severity="error" :closable="false">{{ errorMsg }}</Message>

    <SectionCard title="Thông tin cơ bản" icon="pi pi-user">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <FormField label="Họ và tên" required :error="errors.full_name">
          <InputText v-model="form.full_name" class="w-full" placeholder="Nguyễn Văn A" />
        </FormField>
        <FormField label="Ngày sinh" required :error="errors.dob">
          <DatePicker v-model="dobDate" date-format="dd/mm/yy" show-icon fluid :max-date="today" />
        </FormField>
        <FormField label="Giới tính" required :error="errors.gender">
          <Select
            v-model="form.gender"
            :options="genderOptions"
            option-label="label"
            option-value="value"
            placeholder="-- Chọn --"
            fluid
          />
        </FormField>
      </div>
    </SectionCard>

    <SectionCard title="Thông tin công ty" icon="pi pi-building">
      <div class="mb-4 flex items-center gap-3">
        <ToggleSwitch v-model="hasCompany" input-id="has-company" />
        <label for="has-company" class="cursor-pointer text-sm font-medium">
          {{ hasCompany ? 'Có công ty' : 'Cá nhân' }}
        </label>
      </div>

      <div v-if="hasCompany" class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField label="Công ty" required :error="errors.company">
          <Select
            v-model="form.company"
            :options="companies"
            option-label="name"
            option-value="id"
            placeholder="-- Chọn công ty --"
            filter
            fluid
          />
        </FormField>
        <FormField
          label="Mã nhân viên"
          required
          :error="errors.employee_code"
          help-text="Bắt buộc và duy nhất trong công ty"
        >
          <InputText v-model="form.employee_code" class="w-full" placeholder="NV-001" />
        </FormField>
        <FormField label="Phòng ban">
          <InputText v-model="form.department" class="w-full" />
        </FormField>
        <FormField label="Ngày vào làm">
          <DatePicker v-model="startDate" date-format="dd/mm/yy" show-icon fluid />
        </FormField>
      </div>
    </SectionCard>

    <SectionCard title="Giấy tờ tùy thân" icon="pi pi-id-card">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <FormField label="CCCD/CMND" :error="errors.cccd" help-text="9 hoặc 12 chữ số">
          <InputText v-model="form.cccd" class="w-full" />
        </FormField>
        <FormField label="Ngày cấp">
          <DatePicker v-model="cccdIssuedDate" date-format="dd/mm/yy" show-icon fluid />
        </FormField>
        <FormField label="Nơi cấp">
          <InputText v-model="form.cccd_issued_place" class="w-full" />
        </FormField>
      </div>
    </SectionCard>

    <SectionCard title="Liên hệ" icon="pi pi-phone">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <FormField label="Địa chỉ">
          <InputText v-model="form.address" class="w-full" />
        </FormField>
        <FormField label="Số điện thoại">
          <InputText v-model="form.phone" class="w-full" placeholder="090xxxxxxx" />
        </FormField>
        <FormField label="Email" :error="errors.email">
          <InputText v-model="form.email" type="email" class="w-full" />
        </FormField>
        <FormField label="Ghi chú" class="md:col-span-3">
          <Textarea v-model="form.notes" rows="2" class="w-full" />
        </FormField>
      </div>
    </SectionCard>

    <div class="flex justify-end gap-2">
      <Button type="button" label="Hủy" severity="secondary" @click="$emit('cancel')" />
      <Button type="submit" :label="submitLabel" :loading="submitting" />
    </div>
  </form>
</template>

<script setup lang="ts">
import { reactive, ref, computed, watch } from 'vue'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import ToggleSwitch from 'primevue/toggleswitch'
import Button from 'primevue/button'
import Message from 'primevue/message'
import FormField from '@/components/common/FormField.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import type { Company, Patient, PatientInput } from '@/types'
import { isValidCccd } from '@/utils/format'

const props = defineProps<{
  modelValue?: Patient | null
  companies: Company[]
  submitting?: boolean
  submitLabel?: string
  errorMsg?: string
}>()

const emit = defineEmits<{
  submit: [payload: PatientInput]
  cancel: []
}>()

const submitLabel = computed(() => props.submitLabel ?? 'Lưu')
const today = new Date()

const genderOptions = [
  { label: 'Nam', value: 'M' },
  { label: 'Nữ', value: 'F' },
]

const hasCompany = ref(true)
const errors = reactive<Record<string, string>>({})

const form = reactive<PatientInput>({
  full_name: '',
  dob: '',
  gender: '',
  company: null,
  employee_code: '',
  department: '',
  start_date: null,
  cccd: '',
  cccd_issued_date: null,
  cccd_issued_place: '',
  address: '',
  phone: '',
  email: '',
  notes: '',
})

// Date <-> ISO string adapters
function toDate(value: string | null | undefined): Date | null {
  return value ? new Date(value) : null
}
function toIso(date: Date | null): string | null {
  if (!date) return null
  return date.toISOString().slice(0, 10)
}

const dobDate = ref<Date | null>(null)
const startDate = ref<Date | null>(null)
const cccdIssuedDate = ref<Date | null>(null)

watch(dobDate, (d) => (form.dob = toIso(d) ?? ''))
watch(startDate, (d) => (form.start_date = toIso(d)))
watch(cccdIssuedDate, (d) => (form.cccd_issued_date = toIso(d)))

watch(
  () => props.modelValue,
  (patient) => {
    if (!patient) return
    Object.assign(form, {
      full_name: patient.full_name,
      dob: patient.dob,
      gender: patient.gender,
      company: patient.company,
      employee_code: patient.employee_code ?? '',
      department: patient.department,
      start_date: patient.start_date,
      cccd: patient.cccd,
      cccd_issued_date: patient.cccd_issued_date,
      cccd_issued_place: patient.cccd_issued_place,
      address: patient.address,
      phone: patient.phone,
      email: patient.email,
      notes: patient.notes,
    })
    hasCompany.value = !!patient.company
    dobDate.value = toDate(patient.dob)
    startDate.value = toDate(patient.start_date)
    cccdIssuedDate.value = toDate(patient.cccd_issued_date)
  },
  { immediate: true },
)

function validate(): boolean {
  Object.keys(errors).forEach((k) => delete errors[k])
  if (!form.full_name) errors.full_name = 'Vui lòng nhập họ tên'
  if (!form.dob) errors.dob = 'Vui lòng chọn ngày sinh'
  if (!form.gender) errors.gender = 'Vui lòng chọn giới tính'
  if (hasCompany.value) {
    if (!form.company) errors.company = 'Vui lòng chọn công ty'
    if (!form.employee_code) errors.employee_code = 'Mã nhân viên là bắt buộc khi có công ty'
  }
  if (form.cccd && !isValidCccd(form.cccd)) errors.cccd = 'CCCD phải là 9 hoặc 12 chữ số'
  if (form.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email))
    errors.email = 'Email không hợp lệ'
  return Object.keys(errors).length === 0
}

function onSubmit(): void {
  if (!validate()) return
  const payload: PatientInput = { ...form }
  if (!hasCompany.value) {
    payload.company = null
    payload.employee_code = ''
  }
  emit('submit', payload)
}
</script>
