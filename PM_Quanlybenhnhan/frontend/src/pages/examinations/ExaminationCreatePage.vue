<template>
  <div>
    <PageHeader title="Tạo lượt khám mới" subtitle="Tạo lượt khám bệnh cho bệnh nhân" />

    <Stepper :value="step" linear>
      <StepList>
        <Step value="patient">Chọn bệnh nhân</Step>
        <Step value="package">Chọn gói khám</Step>
        <Step value="exam">Thông tin khám</Step>
      </StepList>
      <StepPanels>
        <StepPanel value="patient">
          <SectionCard>
            <div class="mb-4">
              <SearchBar v-model="patientSearch" placeholder="Tìm bệnh nhân..." />
            </div>
            <div class="mb-4 flex flex-wrap gap-2">
              <Button
                v-if="selectedPatient"
                label="Tiếp tục"
                icon="pi pi-arrow-right"
                @click="step = 'package'"
              />
            </div>
            <DataTable
              :columns="patientColumns"
              :data="filteredPatients"
              :loading="patientLoading"
              @row-click="onSelectPatient"
            >
              <template #body-full_name="{ data }">
                <span class="font-medium">{{ data.full_name }}</span>
              </template>
              <template #body-gender="{ value }">{{ genderLabel(value) }}</template>
              <template #body-company="{ data }">{{ data.company_detail?.name || 'Cá nhân' }}</template>
            </DataTable>
          </SectionCard>
        </StepPanel>

        <StepPanel value="package">
          <SectionCard>
            <p v-if="selectedPatient" class="mb-4 text-text-muted">
              Bệnh nhân: <strong>{{ selectedPatient.full_name }}</strong>
            </p>
            <div class="mb-4">
              <label class="mb-1 block text-sm font-medium text-text-body">Gói khám</label>
              <Select
                v-model="selectedCompanyPackage"
                :options="companyPackages"
                option-label="label"
                option-value="value"
                placeholder="-- Chọn gói khám --"
                filter
                class="w-full sm:w-96"
                @update:model-value="onPackageSelected"
              >
                <template #option="{ option }">
                  {{ option.label }} ({{ examTypeLabel(option.examType) }})
                </template>
              </Select>
            </div>
            <div class="flex gap-2">
              <Button label="Quay lại" severity="secondary" outlined @click="step = 'patient'" />
              <Button
                label="Tiếp tục"
                icon="pi pi-arrow-right"
                :disabled="!selectedCompanyPackage"
                @click="step = 'exam'"
              />
            </div>
          </SectionCard>
        </StepPanel>

        <StepPanel value="exam">
          <SectionCard>
            <div class="mb-4 flex flex-wrap gap-3">
              <FormField label="Ngày khám" required>
                <DatePicker
                  v-model="examDate"
                  date-format="dd/mm/yy"
                  show-icon
                  class="w-full sm:w-48"
                />
              </FormField>
              <FormField label="Bác sĩ phụ trách">
                <Select
                  v-model="selectedDoctor"
                  :options="doctorOptions"
                  option-label="full_name"
                  option-value="id"
                  placeholder="-- Chọn bác sĩ --"
                  show-clear
                  filter
                  class="w-full sm:w-56"
                />
              </FormField>
            </div>

            <Message v-if="serverError" severity="error" :closable="false" class="mb-4">
              {{ serverError }}
            </Message>

            <div class="flex gap-2">
              <Button label="Quay lại" severity="secondary" outlined @click="step = 'package'" />
              <Button
                label="Lưu nháp"
                icon="pi pi-save"
                severity="secondary"
                :loading="saving"
                @click="createExam"
              />
              <Button
                label="Tạo và tiếp tục"
                icon="pi pi-check"
                :loading="saving"
                @click="createExam"
            />              
            </div>
          </SectionCard>
        </StepPanel>
      </StepPanels>
    </Stepper>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import Stepper from 'primevue/stepper'
import StepList from 'primevue/steplist'
import Step from 'primevue/step'
import StepPanels from 'primevue/steppanels'
import StepPanel from 'primevue/steppanel'
import Message from 'primevue/message'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import SearchBar from '@/components/common/SearchBar.vue'
import DataTable from '@/components/common/DataTable.vue'
import FormField from '@/components/common/FormField.vue'
import { useExamStore } from '@/stores/exams'
import { usePatientStore } from '@/stores/patients'
import { packagesService } from '@/services/packages'
import { useToast } from '@/composables/useToast'
import { extractError } from '@/services/api'
import api from '@/services/api'
import { examTypeLabel, genderLabel } from '@/utils/format'
import type { Patient, ColumnDef, ExamType, CompanyExamPackage } from '@/types'

const router = useRouter()
const examStore = useExamStore()
const patientStore = usePatientStore()
const toast = useToast()

const step = ref('patient')
const patientSearch = ref('')
const patientLoading = ref(false)
const selectedPatient = ref<Patient | null>(null)
const selectedCompanyPackage = ref<string | null>(null)
const companyPackages = ref<{ label: string; value: string; examType: ExamType }[]>([])
const examDate = ref<Date>(new Date())
const selectedDoctor = ref<string | null>(null)
const doctorOptions = ref<{ id: string; full_name: string }[]>([])
const saving = ref(false)
const serverError = ref('')

const patientColumns: ColumnDef[] = [
  { field: 'employee_code', header: 'Mã NV', width: '8rem' },
  { field: 'full_name', header: 'Họ tên', sortable: true },
  { field: 'dob', header: 'Ngày sinh', width: '9rem' },
  { field: 'gender', header: 'Giới tính', width: '7rem' },
  { field: 'company', header: 'Công ty' },
]

const filteredPatients = computed(() => {
  const all = patientStore.list
  if (!patientSearch.value) return all
  const q = patientSearch.value.toLowerCase()
  return all.filter(
    (p) =>
      p.full_name.toLowerCase().includes(q) ||
      (p.employee_code && p.employee_code.toLowerCase().includes(q)) ||
      (p.cccd && p.cccd.includes(q)) ||
      (p.phone && p.phone.includes(q)),
  )
})

function onSelectPatient(row: unknown) {
  selectedPatient.value = row as Patient
}

async function onPackageSelected() {
  // auto-fill exam_type is handled in createExam
}

async function loadCompanyPackages() {
  if (!selectedPatient.value?.company) return
  try {
    const { data } = await packagesService.listCompanyPackages(selectedPatient.value.company)
    const result: CompanyExamPackage[] = Array.isArray(data) ? data : ((data as { results: CompanyExamPackage[] }).results || [])
    companyPackages.value = result.map((cp) => ({
      label: `${cp.package_detail?.name} (${examTypeLabel(cp.package_detail?.exam_type)})`,
      value: cp.id,
      examType: cp.package_detail?.exam_type as ExamType,
    }))
  } catch {
    companyPackages.value = []
  }
}

async function loadDoctors() {
  try {
    const { data } = await api.get('/auth/users/?role=doctor')
    const arr = Array.isArray(data) ? data : (data as { results: unknown[] })?.results || []
    doctorOptions.value = arr as { id: string; full_name: string }[]
  } catch {
    doctorOptions.value = []
  }
}

async function createExam() {
  if (!selectedPatient.value) return
  saving.value = true
  serverError.value = ''
  try {
    const selectedPkg = companyPackages.value.find(p => p.value === selectedCompanyPackage.value)
    const examData = await examStore.create({
      patient: selectedPatient.value.id,
      company_exam_package: selectedCompanyPackage.value || undefined,
      exam_type: selectedPkg?.examType ?? 'periodic',
      exam_date: examDate.value.toISOString().slice(0, 10),
      doctor: selectedDoctor.value || undefined,
    })
    toast.showSuccess('Đã tạo lượt khám')
    router.push({ name: 'exam-edit', params: { id: examData.id } })
  } catch (err) {
    serverError.value = extractError(err, 'Lỗi khi tạo lượt khám')
  } finally {
    saving.value = false
  }
}

watch(() => selectedPatient.value, (patient) => {
  if (patient) loadCompanyPackages()
})

onMounted(() => {
  patientStore.fetchList()
  loadDoctors()
})
</script>
