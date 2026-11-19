<template>
  <div>
    <PageHeader title="Tạo báo cáo mới">
      <template #actions>
        <Button
          label="Quay lại"
          icon="pi pi-arrow-left"
          severity="secondary"
          @click="router.push({ name: 'report-list' })"
        />
      </template>
    </PageHeader>

    <SectionCard title="Thông tin báo cáo">
      <div class="flex flex-col gap-4">
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <FormField label="Công ty" required>
            <Select
              v-model="form.company_id"
              :options="companyOptions"
              option-label="name"
              option-value="id"
              placeholder="Chọn công ty"
              show-clear
              filter
              :loading="companyStore.loading"
              @change="onCompanyChange"
            />
          </FormField>

          <FormField label="Gói khám" required>
            <Select
              v-model="form.exam_package_id"
              :options="packageOptions"
              option-label="label"
              option-value="value"
              placeholder="Chọn gói khám"
              :disabled="!form.company_id"
              :loading="packageStore.loading"
            />
          </FormField>
        </div>

        <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
          <FormField label="Ngày khám">
            <DatePicker
              v-model="examDatePicker"
              placeholder="dd/mm/yy"
              date-format="dd/mm/yy"
              show-icon
            />
          </FormField>

          <FormField label="Loại báo cáo" required>
            <Select
              v-model="form.report_type"
              :options="reportTypeOptions"
              option-label="label"
              option-value="value"
              placeholder="Chọn loại báo cáo"
            />
          </FormField>

          <FormField label="Định dạng" required>
            <Select
              v-model="form.output_format"
              :options="formatOptions"
              option-label="label"
              option-value="value"
              placeholder="Chọn định dạng"
            />
          </FormField>
        </div>

        <FormField
          label="Mẫu báo cáo"
          :help-text="templateHint"
        >
          <Select
            v-model="form.template_id"
            :options="templateOptions"
            option-label="label"
            option-value="value"
            :placeholder="'Chọn mẫu báo cáo'"
            :loading="templatesLoading"
            show-clear
          />
        </FormField>

        <div v-if="errorMsg" class="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
          {{ errorMsg }}
        </div>

        <div class="flex gap-2">
          <Button
            label="Tạo báo cáo"
            icon="pi pi-cog"
            :loading="submitting"
            :disabled="!canSubmit"
            @click="handleSubmit"
          />
          <Button
            label="Hủy"
            severity="secondary"
            :disabled="submitting"
            @click="router.push({ name: 'report-list' })"
          />
        </div>
      </div>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import FormField from '@/components/common/FormField.vue'
import { useReportStore } from '@/stores/reports'
import { useCompanyStore } from '@/stores/companies'
import { usePackageStore } from '@/stores/packages'
import { reportTemplatesService } from '@/services/reports'
import { useToast } from '@/composables/useToast'
import { extractError } from '@/services/api'
import type { ReportType, ReportOutputFormat, ReportTemplateSummary } from '@/types'

interface CompanyOption {
  id: string
  name: string
}

interface PackageOption {
  label: string
  value: string
}

const router = useRouter()
const reportStore = useReportStore()
const companyStore = useCompanyStore()
const packageStore = usePackageStore()
const toast = useToast()

function todayIso(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const submitting = ref(false)
const errorMsg = ref('')
const templates = ref<ReportTemplateSummary[]>([])
const templatesLoading = ref(false)

const form = reactive({
  company_id: '' as string,
  exam_package_id: '' as string,
  exam_date: todayIso(),
  report_type: 'clinical_detail' as ReportType,
  output_format: 'xlsx' as ReportOutputFormat,
  template_id: '' as string,
})

const examDatePicker = ref<Date | null>(new Date())

watch(examDatePicker, (d) => {
  form.exam_date = d ? d.toISOString().slice(0, 10) : ''
})

const reportTypeOptions = [
  { label: 'Báo Cáo Chi Tiết', value: 'clinical_detail' },
  { label: 'Báo Cáo Tổng Hợp Công Ty', value: 'company_summary' },
  { label: 'Báo Cáo Bệnh Nghề Nghiệp', value: 'occupational' },
  { label: 'Báo Cáo Chi Phí', value: 'cost' },
]

const formatOptions = [
  { label: 'Excel (.xlsx)', value: 'xlsx' },
  { label: 'HTML (.html)', value: 'html' },
]

const companyOptions = computed<CompanyOption[]>(() => {
  return (companyStore.list as unknown as CompanyOption[]).filter((c) => (c as { is_active?: boolean }).is_active !== false)
})

const packageOptions = computed<PackageOption[]>(() => {
  const pkgs = packageStore.companyPackages[form.company_id] ?? []
  return pkgs
    .filter((p) => p.is_active)
    .map((p) => ({
      label: p.package_detail?.name ?? 'Gói khám',
      value: p.exam_package,
    }))
})

/** Templates matching the selected report type. */
const templateOptions = computed(() =>
  templates.value
    .filter((t) => t.report_type === form.report_type && t.is_active)
    .map((t) => ({
      label: t.is_default ? `${t.name} (mặc định)` : t.name,
      value: t.id,
    })),
)

const templateHint = computed(() => {
  if (form.template_id) return ''
  const fallback = templates.value.find(
    (t) => t.report_type === form.report_type && t.is_default && t.is_active,
  )
  return fallback
    ? `Bỏ trống sẽ dùng mẫu mặc định: ${fallback.name}`
    : 'Chưa có mẫu mặc định cho loại báo cáo này — vui lòng chọn một mẫu.'
})

const canSubmit = computed(() => {
  return Boolean(
    form.company_id && form.exam_package_id && form.report_type && form.output_format,
  )
})

async function onCompanyChange(): Promise<void> {
  form.exam_package_id = ''
  if (form.company_id) {
    await packageStore.fetchCompanyPackages(form.company_id)
    form.exam_package_id = packageOptions.value[0]?.value ?? ''
  }
}

// A template belongs to exactly one report type.
watch(
  () => form.report_type,
  () => {
    form.template_id = ''
  },
)

async function loadTemplates(): Promise<void> {
  templatesLoading.value = true
  try {
    const { data } = await reportTemplatesService.list({
      is_active: true,
      page_size: 200,
    })
    templates.value = data.results ?? []
  } catch {
    // Non-fatal: generation still works via the default template / Excel.
    templates.value = []
  } finally {
    templatesLoading.value = false
  }
}

async function handleSubmit(): Promise<void> {
  if (!canSubmit.value) return
  errorMsg.value = ''
  submitting.value = true
  try {
    const payload: Parameters<typeof reportStore.generate>[0] = {
      company_id: form.company_id,
      exam_package_id: form.exam_package_id,
      report_type: form.report_type,
      output_format: form.output_format,
    }
    if (form.exam_date) {
      payload.exam_date = form.exam_date
    }
    if (form.template_id) {
      payload.template_id = form.template_id
    }
    await reportStore.generate(payload)
    toast.showSuccess('Đã tạo yêu cầu báo cáo. Báo cáo đang được xử lý.')
    router.push({ name: 'report-list' })
  } catch (err) {
    errorMsg.value = extractError(err, 'Không thể tạo báo cáo')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  companyStore.filters.page_size = 200
  await Promise.all([companyStore.fetchList(), loadTemplates()])
})
</script>
