<template>
  <div>
    <PageHeader
      title="Đồng bộ CSDLKSK"
      subtitle="Liên thông dữ liệu khám sức khỏe lên Cổng dữ liệu sức khỏe Quốc gia"
    >
      <template #actions>
        <Button
          label="Mapping XML"
          icon="pi pi-link"
          severity="secondary"
          outlined
          @click="router.push('/sync/mapping')"
        />
        <Button
          label="Chữ ký số"
          icon="pi pi-pencil"
          severity="secondary"
          outlined
          @click="router.push('/sync/signatures')"
        />
      </template>
    </PageHeader>

    <div class="flex flex-col gap-6">
      <!-- ===================== Cấu hình ===================== -->
      <SectionCard title="Cấu hình liên thông" icon="pi pi-cog" collapsible default-collapsed>
        <Tabs v-model:value="activeConfigEnv">
          <TabList>
            <Tab value="sandbox">
              <span class="flex items-center gap-2">
                Sandbox (test)
                <Tag :value="configs.sandbox?.is_configured ? 'Đã cấu hình' : 'Chưa cấu hình'" :severity="configs.sandbox?.is_configured ? 'success' : 'warn'" />
              </span>
            </Tab>
            <Tab value="production">
              <span class="flex items-center gap-2">
                Production (thật)
                <Tag :value="configs.production?.is_configured ? 'Đã cấu hình' : 'Chưa cấu hình'" :severity="configs.production?.is_configured ? 'success' : 'warn'" />
              </span>
            </Tab>
          </TabList>

          <TabPanels>
            <TabPanel value="sandbox">
              <ConfigForm
                v-model="sandboxForm"
                :config="configs.sandbox"
                :saving="savingConfig"
                @save="handleSaveConfig('sandbox')"
              />
            </TabPanel>
            <TabPanel value="production">
              <ConfigForm
                v-model="productionForm"
                :config="configs.production"
                :saving="savingConfig"
                @save="handleSaveConfig('production')"
              />
            </TabPanel>
          </TabPanels>
        </Tabs>
      </SectionCard>

      <!-- ===================== Phạm vi đồng bộ ===================== -->
      <SectionCard title="Phạm vi đồng bộ" icon="pi pi-sync">
        <div class="flex flex-col gap-4">
          <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField label="Môi trường đồng bộ" required>
              <div class="flex rounded-lg border border-gray-300 p-1">
                <button
                  type="button"
                  class="flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors"
                  :class="
                    scope.environment === 'sandbox'
                      ? 'bg-primary text-white'
                      : 'text-text-body hover:bg-gray-100'
                  "
                  @click="scope.environment = 'sandbox'"
                >
                  <i class="pi pi-flask mr-1" /> Sandbox
                </button>
                <button
                  type="button"
                  class="flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors"
                  :class="
                    scope.environment === 'production'
                      ? 'bg-danger text-white'
                      : 'text-text-body hover:bg-gray-100'
                  "
                  @click="scope.environment = 'production'"
                >
                  <i class="pi pi-globe mr-1" /> Production
                </button>
              </div>
            </FormField>

            <FormField label="Phạm vi" required>
              <Select
                v-model="scope.scope_type"
                :options="scopeOptions"
                option-label="label"
                option-value="value"
                placeholder="Chọn phạm vi"
                @change="onScopeChange"
              />
            </FormField>

            <FormField v-if="scope.scope_type === 'company'" label="Công ty" required>
              <Select
                v-model="scope.company_id"
                :options="companyOptions"
                option-label="name"
                option-value="id"
                placeholder="Chọn công ty"
                show-clear
                filter
                :loading="companyStore.loading"
              />
            </FormField>

            <FormField v-else-if="scope.scope_type === 'patient'" label="Bệnh nhân lẻ" required>
              <Select
                v-model="scope.patient_id"
                :options="walkinOptions"
                option-label="label"
                option-value="value"
                placeholder="Chọn bệnh nhân"
                show-clear
                filter
                :loading="patientsLoading"
              />
            </FormField>
          </div>

          <p class="text-sm text-text-muted">
            {{
              scope.scope_type === 'company'
                ? 'Sẽ lấy toàn bộ lượt khám thuộc gói khám đang active của công ty.'
                : 'Sẽ lấy toàn bộ lượt khám của bệnh nhân đã chọn.'
            }}
          </p>

          <div class="flex gap-2">
            <Button
              label="Kiểm tra"
              icon="pi pi-search"
              severity="secondary"
              :loading="validating"
              :disabled="!canValidate"
              @click="handleValidate"
            />
            <Button
              label="Đồng bộ ngay"
              icon="pi pi-cloud-upload"
              :loading="triggering"
              :disabled="!canTrigger"
              @click="handleTrigger"
            />
          </div>
          <p class="text-xs text-text-muted">
            {{
              usbReady
                ? 'TokenService đang chạy. Bấm đồng bộ sẽ mở cửa sổ chọn chứng thư bệnh viện, rồi hộp nhập PIN.'
                : 'Chưa thấy TokenService. Cắm USB của cơ sở khám và mở TokenService ở khay hệ thống.'
            }}
          </p>

          <!-- Kết quả kiểm tra -->
          <div v-if="validation" class="rounded-md border border-gray-200 p-4">
            <div class="mb-2 flex flex-wrap items-center gap-3">
              <span class="text-sm text-text-body">
                Tổng: <strong>{{ validation.total }}</strong> — Chưa đồng bộ:
                <strong>{{ validation.eligible }}</strong>
                <template v-if="(validation.already_synced_count ?? 0) > 0">
                  — Đã đồng bộ: <strong>{{ validation.already_synced_count }}</strong>
                </template>
              </span>
              <Tag
                v-if="validation.total === 0"
                value="Không có lượt khám trong phạm vi"
                severity="warn"
              />
              <Tag
                v-else-if="(validation.signature_issues?.length ?? 0) > 0"
                value="Thiếu chữ ký hồ sơ"
                severity="warn"
              />
              <Tag
                v-else-if="validation.eligible === 0"
                value="Tất cả đã đồng bộ"
                severity="info"
              />
              <Tag v-else value="Sẵn sàng đồng bộ" severity="success" />
            </div>

            <p v-if="validation.total === 0" class="text-sm text-text-muted">
              Không tìm thấy lượt khám nào cho công ty/bệnh nhân và khoảng thời gian đã chọn. Vui
              lòng kiểm tra lại lựa chọn.
            </p>

            <div
              v-if="(validation.signature_issues?.length ?? 0) > 0"
              class="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
            >
              <p class="font-semibold">Chưa đồng bộ được</p>
              <ul class="mt-1 list-disc pl-5">
                <li v-for="(issue, idx) in validation.signature_issues" :key="idx">{{ issue }}</li>
              </ul>
            </div>

            <div
              v-if="(validation.eligible_exams ?? []).length > 0"
              class="mt-3 overflow-hidden rounded-md border border-emerald-200"
            >
              <div class="bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700">
                Chưa đồng bộ ({{ validation.eligible_exams.length }})
              </div>
              <table class="w-full text-sm">
                <thead class="bg-gray-50 text-left text-text-muted">
                  <tr>
                    <th class="px-3 py-2">Bệnh nhân</th>
                    <th class="px-3 py-2">Bác sĩ</th>
                    <th class="px-3 py-2">Ngày khám</th>
                    <th class="px-3 py-2">Trạng thái</th>
                    <th class="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="exam in validation.eligible_exams"
                    :key="exam.id"
                    class="border-t border-gray-100"
                  >
                    <td class="px-3 py-2">{{ exam.patient }}</td>
                    <td class="px-3 py-2">{{ exam.doctor || '—' }}</td>
                    <td class="px-3 py-2">{{ formatDate(exam.exam_date) }}</td>
                    <td class="px-3 py-2">
                      <StatusBadge :status="exam.status" size="sm" />
                    </td>
                    <td class="px-3 py-2 text-right">
                      <div class="flex justify-end gap-2">
                        <Button
                          label="Mở"
                          icon="pi pi-external-link"
                          size="small"
                          severity="secondary"
                          @click="openExam(exam.id)"
                        />
                        <Button
                          label="Đồng bộ"
                          icon="pi pi-cloud-upload"
                          size="small"
                          :loading="syncingExamId === exam.id"
                          :disabled="
                            !!syncingExamId ||
                            triggering ||
                            (validation.signature_issues?.length ?? 0) > 0
                          "
                          @click="handleTriggerExam(exam.id)"
                        />
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div
              v-if="(validation.already_synced ?? []).length > 0"
              class="mt-3 overflow-hidden rounded-md border border-gray-200"
            >
              <button
                type="button"
                class="flex w-full items-center gap-2 bg-gray-50 px-3 py-2 text-left text-sm font-semibold text-text-muted hover:bg-gray-100"
                :aria-expanded="!alreadySyncedCollapsed"
                :aria-label="alreadySyncedCollapsed ? 'Mở rộng' : 'Thu gọn'"
                @click="alreadySyncedCollapsed = !alreadySyncedCollapsed"
              >
                <span class="flex-1">
                  Đã đồng bộ thành công trước đó ({{ validation.already_synced_count ?? validation.already_synced?.length ?? 0 }}) — bỏ qua khi
                  đồng bộ tất cả
                </span>
                <i :class="alreadySyncedCollapsed ? 'pi pi-chevron-down' : 'pi pi-chevron-up'" />
              </button>
              <table v-show="!alreadySyncedCollapsed" class="w-full text-sm">
                <thead class="bg-gray-50 text-left text-text-muted">
                  <tr>
                    <th class="px-3 py-2">Bệnh nhân</th>
                    <th class="px-3 py-2">Bác sĩ</th>
                    <th class="px-3 py-2">Ngày khám</th>
                    <th class="px-3 py-2">Trạng thái</th>
                    <th class="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="exam in validation.already_synced ?? []"
                    :key="exam.id"
                    class="border-t border-gray-100"
                  >
                    <td class="px-3 py-2">{{ exam.patient }}</td>
                    <td class="px-3 py-2">{{ exam.doctor || '—' }}</td>
                    <td class="px-3 py-2">{{ formatDate(exam.exam_date) }}</td>
                    <td class="px-3 py-2">
                      <StatusBadge :status="exam.status" size="sm" />
                    </td>
                    <td class="px-3 py-2 text-right">
                      <div class="flex justify-end gap-2">
                        <Button
                          label="Mở"
                          icon="pi pi-external-link"
                          size="small"
                          severity="secondary"
                          @click="openExam(exam.id)"
                        />
                        <Button
                          label="Đồng bộ lại"
                          icon="pi pi-cloud-upload"
                          size="small"
                          :loading="syncingExamId === exam.id"
                          :disabled="!!syncingExamId || triggering"
                          @click="handleTriggerExam(exam.id)"
                        />
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </SectionCard>

      <!-- ===================== Lịch sử ===================== -->
      <SectionCard title="Lịch sử đồng bộ" icon="pi pi-history">
        <template #actions>
          <Button
            label="Làm mới"
            icon="pi pi-refresh"
            size="small"
            severity="secondary"
            :loading="store.jobsLoading"
            @click="store.fetchJobs()"
          />
        </template>
        <DataTable :columns="jobColumns" :data="store.jobs" :loading="store.jobsLoading">
          <template #body-status="{ data }">
            <StatusBadge :status="data.status" size="sm" />
          </template>
          <template #body-environment_display="{ data }">
            {{ data.environment_display || '—' }}
          </template>
          <template #body-scope_type_display="{ data }">
            {{ data.scope_type_display }}
          </template>
          <template #body-scope="{ data }">
            {{
              data.examination_patient
                ? `1 lượt: ${data.examination_patient}`
                : data.company_name || data.patient_name || '—'
            }}
          </template>
          <template #body-stats="{ data }">
            <span class="text-sm">
              OK {{ data.success_count ?? 0 }} / Lỗi {{ data.failed_count ?? 0 }}
              <template v-if="(data.skipped_count ?? 0) > 0">
                / Bỏ qua {{ data.skipped_count }}
              </template>
            </span>
          </template>
          <template #body-created_at="{ data }">
            {{ formatDateTime(data.created_at) }}
          </template>
          <template #body-error_message="{ data }">
            <span v-if="data.error_message" class="text-danger">{{ data.error_message }}</span>
            <span v-else>—</span>
          </template>
        </DataTable>
      </SectionCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Select from 'primevue/select'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import Tag from 'primevue/tag'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import FormField from '@/components/common/FormField.vue'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import ConfigForm, { type ConfigFormModel } from '@/components/sync/ConfigForm.vue'
import { useNationalSyncStore } from '@/stores/nationalsync'
import { useCompanyStore } from '@/stores/companies'
import { patientsService } from '@/services/patients'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { extractError } from '@/services/api'
import { nationalSyncService } from '@/services/nationalsync'
import { signXmlWithUsbToken, usbSignerStatus } from '@/services/usbSigner'
import type { SyncConfig, SyncEnvironment, SyncScopeType, SyncValidationResult } from '@/types'

const store = useNationalSyncStore()
const companyStore = useCompanyStore()
const toast = useToast()
const confirm = useConfirm()
const router = useRouter()

const scopeOptions = [
  { label: 'Theo công ty', value: 'company' },
  { label: 'Theo bệnh nhân lẻ', value: 'patient' },
]

function blankForm(): ConfigFormModel {
  return {
    api_base_url: '',
    username: '',
    password: '',
    facility_code: '',
    sender_id: '',
    receiver_id: 'TTYQG',
    version: '1.0.6',
    private_key: '',
    is_active: false,
  }
}

const activeConfigEnv = ref<SyncEnvironment>('sandbox')
const sandboxForm = reactive<ConfigFormModel>(blankForm())
const productionForm = reactive<ConfigFormModel>(blankForm())

const configs = computed(() => store.configs)

const scope = reactive<{
  environment: SyncEnvironment
  scope_type: SyncScopeType
  company_id: string
  patient_id: string
}>({
  environment: 'sandbox',
  scope_type: 'company',
  company_id: '',
  patient_id: '',
})

const savingConfig = ref(false)
const validating = ref(false)
const triggering = ref(false)
const usbReady = ref(false)
const syncingExamId = ref<string | null>(null)
const validation = ref<SyncValidationResult | null>(null)
const alreadySyncedCollapsed = ref(true)

const walkinPatients = ref<{ label: string; value: string }[]>([])
const patientsLoading = ref(false)

const companyOptions = computed(() =>
  (companyStore.list as unknown as { id: string; name: string; is_active?: boolean }[]).filter(
    (c) => c.is_active !== false,
  ),
)

const walkinOptions = computed(() => walkinPatients.value)

const jobColumns = [
  { field: 'status', header: 'Trạng thái', sortable: false },
  { field: 'environment_display', header: 'Môi trường', sortable: false },
  { field: 'scope_type_display', header: 'Phạm vi', sortable: false },
  { field: 'scope', header: 'Đối tượng', sortable: false },
  { field: 'stats', header: 'Kết quả', sortable: false },
  { field: 'created_at', header: 'Tạo lúc', sortable: false },
  { field: 'error_message', header: 'Lỗi', sortable: false },
]

const canValidate = computed(() => {
  if (scope.scope_type === 'company') return !!scope.company_id
  return !!scope.patient_id
})

const canTrigger = computed(() => {
  if (!canValidate.value) return false
  if (!validation.value || validation.value.eligible === 0) return false
  if ((validation.value.signature_issues?.length ?? 0) > 0) return false
  return true
})

function buildTriggerPayload(examinationId?: string) {
  return {
    environment: scope.environment,
    scope_type: scope.scope_type,
    company_id: scope.scope_type === 'company' ? scope.company_id || null : null,
    patient_id: scope.scope_type === 'patient' ? scope.patient_id || null : null,
    examination_id: examinationId || null,
  }
}

function fillForm(target: ConfigFormModel, c: SyncConfig | undefined): void {
  target.api_base_url = c?.api_base_url ?? ''
  target.username = c?.username ?? ''
  target.password = ''
  target.facility_code = c?.facility_code ?? ''
  target.sender_id = c?.sender_id ?? ''
  target.receiver_id = c?.receiver_id ?? 'TTYQG'
  target.version = c?.version ?? '1.0.6'
  target.private_key = ''
  target.is_active = c?.is_active ?? false
}

function fillConfigForms(): void {
  fillForm(sandboxForm, configs.value.sandbox)
  fillForm(productionForm, configs.value.production)
}

function onScopeChange(): void {
  validation.value = null
  if (scope.scope_type === 'company') scope.patient_id = ''
  else scope.company_id = ''
}

async function handleSaveConfig(environment: SyncEnvironment): Promise<void> {
  const form = environment === 'sandbox' ? sandboxForm : productionForm
  savingConfig.value = true
  try {
    await store.saveConfig({
      environment,
      api_base_url: form.api_base_url || undefined,
      username: form.username,
      password: form.password || undefined,
      facility_code: form.facility_code || undefined,
      sender_id: form.sender_id,
      receiver_id: form.receiver_id || undefined,
      version: form.version || undefined,
      private_key: form.private_key || undefined,
      is_active: form.is_active,
    })
    toast.showSuccess('Đã lưu cấu hình liên thông.')
  } catch (err) {
    toast.showError(extractError(err, 'Không thể lưu cấu hình'))
  } finally {
    savingConfig.value = false
  }
}

async function handleValidate(): Promise<void> {
  validating.value = true
  validation.value = null
  alreadySyncedCollapsed.value = true
  try {
    validation.value = await store.validate(buildTriggerPayload())
  } catch (err) {
    toast.showError(extractError(err, 'Không thể kiểm tra'))
  } finally {
    validating.value = false
  }
}

function syncError(err: unknown, fallback: string): string {
  if (err instanceof Error && !('isAxiosError' in err)) return err.message
  return extractError(err, fallback)
}

async function signPendingExams(
  scopePayload: ReturnType<typeof buildTriggerPayload>,
): Promise<Record<string, string>> {
  const { data } = await nationalSyncService.signingXml(scopePayload)
  if (!data.exams.length) {
    throw new Error('Không có hồ sơ để ký.')
  }
  toast.showInfo('Hãy chọn chứng thư bệnh viện trên cửa sổ Windows, rồi nhập PIN của USB.')
  const signatures: Record<string, string> = {}
  for (const exam of data.exams) {
    signatures[exam.id] = await signXmlWithUsbToken(exam.xml)
  }
  return signatures
}

async function handleTrigger(): Promise<void> {
  if (scope.environment === 'production') {
    const ok = await confirm.require(
      'Xác nhận đẩy dữ liệu Production',
      'Bạn đang đồng bộ dữ liệu thật lên Cổng CSDLKSK (Production). Xác nhận tiếp tục?',
      true,
    )
    if (!ok) return
  }
  triggering.value = true
  try {
    const payload = buildTriggerPayload()
    const cks = await signPendingExams(payload)
    await store.trigger({ ...payload, cks_nguoi_ket_luan: cks })
    toast.showSuccess('Đã ký USB và tạo yêu cầu đồng bộ. Hệ thống đang xử lý.')
    validation.value = null
    await store.fetchJobs()
  } catch (err) {
    toast.showError(syncError(err, 'Không thể đồng bộ'))
  } finally {
    triggering.value = false
  }
}

async function handleTriggerExam(examinationId: string): Promise<void> {
  if (scope.environment === 'production') {
    const ok = await confirm.require(
      'Xác nhận đẩy dữ liệu Production',
      'Bạn đang đồng bộ 1 lượt khám thật lên Cổng CSDLKSK (Production). Xác nhận tiếp tục?',
      true,
    )
    if (!ok) return
  }
  syncingExamId.value = examinationId
  try {
    const payload = buildTriggerPayload(examinationId)
    const cks = await signPendingExams(payload)
    await store.trigger({ ...payload, cks_nguoi_ket_luan: cks })
    toast.showSuccess('Đã ký USB và tạo yêu cầu đồng bộ cho lượt khám. Hệ thống đang xử lý.')
    // Refresh validate list + job history; keep scope selection.
    validation.value = await store.validate(buildTriggerPayload())
    await store.fetchJobs()
  } catch (err) {
    toast.showError(syncError(err, 'Không thể đồng bộ lượt khám'))
  } finally {
    syncingExamId.value = null
  }
}

async function loadWalkinPatients(): Promise<void> {
  patientsLoading.value = true
  try {
    const { data } = await patientsService.list({ has_company: false, page_size: 200 })
    walkinPatients.value = (data.results ?? []).map((p) => ({
      label: [p.full_name, p.cccd, p.phone].filter(Boolean).join(' · '),
      value: p.id,
    }))
  } catch {
    walkinPatients.value = []
  } finally {
    patientsLoading.value = false
  }
}

function openExam(examId: string): void {
  const url = router.resolve({ name: 'exam-edit', params: { id: examId } }).href
  window.open(url, '_blank', 'noopener,noreferrer')
}

function formatDate(iso: string): string {
  if (!iso) return '—'
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${y}`
}

function formatDateTime(iso: string): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('vi-VN')
}

async function refreshUsbStatus(): Promise<void> {
  try {
    const status = await usbSignerStatus()
    usbReady.value = status.ok
  } catch {
    usbReady.value = false
  }
}

onMounted(async () => {
  companyStore.filters.page_size = 200
  await Promise.all([
    store.fetchConfig(),
    store.fetchJobs(),
    companyStore.fetchList(),
    loadWalkinPatients(),
    refreshUsbStatus(),
  ])
  fillConfigForms()
})
</script>
