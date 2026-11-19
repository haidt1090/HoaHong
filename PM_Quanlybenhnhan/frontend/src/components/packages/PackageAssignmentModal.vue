<template>
  <Dialog
    :visible="visible"
    :header="editingPackage ? 'Sửa gói khám' : 'Gán gói khám'"
    modal
    :style="{ width: '42rem' }"
    :breakpoints="{ '960px': '90vw' }"
    @update:visible="$emit('update:visible', $event)"
  >
    <div class="flex flex-col gap-4">
      <Message v-if="errorMsg" severity="error" :closable="false">{{ errorMsg }}</Message>

      <FormField label="Gói khám" required>
        <Select
          v-model="form.exam_package"
          :options="availablePackages"
          option-label="name"
          option-value="id"
          placeholder="-- Chọn gói khám --"
          :disabled="!!editingPackage"
          filter
          fluid
          @change="onPackageChange"
        >
          <template #option="{ option }">
            {{ option.name }} ({{ examTypeLabel(option.exam_type) }})
          </template>
        </Select>
      </FormField>

      <FormField label="Số lượng nhân viên">
        <InputNumber v-model="form.total_employees" :min="0" fluid />
      </FormField>

      <FormField label="Hình thức tính giá" required>
        <PricingModeToggle v-model="form.pricing_mode" />
      </FormField>

      <FormField v-if="form.pricing_mode === 'package_total'" label="Giá trọn gói (VNĐ)">
        <InputNumber v-model="packagePrice" :min="0" mode="decimal" :use-grouping="true" fluid />
      </FormField>

      <div v-else>
        <label class="mb-2 block text-sm font-semibold text-text-body"
          >Bảng giá theo từng chỉ số</label
        >
        <PricingFieldTable
          :rows="fieldRows"
          :loading="loadingFields"
          @total="perFieldTotal = $event"
        />
      </div>
    </div>

    <template #footer>
      <Button label="Hủy" severity="secondary" text @click="$emit('update:visible', false)" />
      <Button label="Lưu" :loading="saving" @click="onSave" />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import InputNumber from 'primevue/inputnumber'
import Button from 'primevue/button'
import Message from 'primevue/message'
import FormField from '@/components/common/FormField.vue'
import PricingModeToggle from './PricingModeToggle.vue'
import PricingFieldTable, { type PricingFieldRow } from './PricingFieldTable.vue'
import { packagesService } from '@/services/packages'
import { examTypeLabel } from '@/utils/format'
import type { ExamPackage, CompanyExamPackage, CompanyExamPackageInput } from '@/types'

const props = defineProps<{
  visible: boolean
  availablePackages: ExamPackage[]
  editingPackage: CompanyExamPackage | null
  saving?: boolean
  errorMsg?: string
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  save: [payload: CompanyExamPackageInput]
}>()

const form = reactive<CompanyExamPackageInput>({
  exam_package: '',
  pricing_mode: 'package_total',
  total_employees: 0,
})

const packagePrice = ref(0)
const perFieldTotal = ref(0)
const fieldRows = ref<PricingFieldRow[]>([])
const loadingFields = ref(false)

async function loadPackageFields(packageId: string): Promise<void> {
  if (!packageId) {
    fieldRows.value = []
    return
  }
  loadingFields.value = true
  try {
    const { data } = await packagesService.getExamPackage(packageId)
    const bindings = data.package_departments ?? []
    const rows: PricingFieldRow[] = []
    for (const binding of bindings) {
      const deptName = binding.department_detail?.name ?? ''
      try {
        const tpl = await packagesService.getTemplate(binding.template)
        for (const field of tpl.data.fields_config ?? []) {
          rows.push({
            department_name: deptName,
            key: `${binding.department}-${field.key}`,
            label: field.label,
            unit: field.unit,
            price: Number(field.default_price) || 0,
          })
        }
      } catch {
        // skip templates that fail to load
      }
    }
    fieldRows.value = rows
  } finally {
    loadingFields.value = false
  }
}

function onPackageChange(): void {
  const pkg = props.availablePackages.find((p) => p.id === form.exam_package)
  if (pkg) packagePrice.value = Number(pkg.default_package_price) || 0
  if (form.pricing_mode === 'per_field') loadPackageFields(form.exam_package)
}

watch(
  () => form.pricing_mode,
  (mode) => {
    if (mode === 'per_field' && form.exam_package) loadPackageFields(form.exam_package)
  },
)

// Reset / populate form when the dialog opens
watch(
  () => props.visible,
  (open) => {
    if (!open) return
    fieldRows.value = []
    perFieldTotal.value = 0
    if (props.editingPackage) {
      const p = props.editingPackage
      form.exam_package = p.exam_package
      form.pricing_mode = p.pricing_mode
      form.total_employees = p.total_employees
      packagePrice.value = Number(p.package_detail?.default_package_price) || 0
      if (p.pricing_mode === 'per_field') loadPackageFields(p.exam_package)
    } else {
      form.exam_package = ''
      form.pricing_mode = 'package_total'
      form.total_employees = 0
      packagePrice.value = 0
    }
  },
)

function onSave(): void {
  emit('save', {
    exam_package: form.exam_package,
    pricing_mode: form.pricing_mode,
    total_employees: form.total_employees || 0,
    is_active: true,
  })
}
</script>
