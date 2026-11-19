<template>
  <div>
    <PageHeader :title="exam ? `Sửa — ${exam.patient_name ?? exam.patient}` : 'Sửa lượt khám'">
      <template #actions>
        <Button label="Quay lại" icon="pi pi-arrow-left" severity="secondary" outlined @click="goBack" />
      </template>
    </PageHeader>

    <LoadingSkeleton v-if="store.loading" type="card" :rows="4" />

    <template v-else-if="formData">
      <Message v-if="saveError" severity="error" :closable="false" class="mb-4">{{ saveError }}</Message>

      <DynamicExamForm
        :departments="editableDepartments"
        :dirty-tabs="dirtyTabs"
        :saving-dept="savingDept"
        :patient-gender="formData.patient_gender ?? null"
        @save-dept="onSaveDept"
        @update-data="onUpdateData"
      />

      <ConclusionSection
        v-if="exam"
        :consultation="localConsultation"
        :conclusion="localConclusion"
        :work-fitness="localWorkFitness"
        :classification="localClassification"
        :disease="localDisease"
        :exam-id="examId"
        :editable="isDoctor()"
        @update:conclusion="localConclusion = $event"
        @update:consultation="localConsultation = $event"
        @update:work-fitness="localWorkFitness = $event"
        @update:classification="localClassification = $event"
        @update:disease="localDisease = $event"
      />

      <ExamStatusActions
        v-if="exam"
        :status="exam.status"
        :role="user?.role ?? null"
        :is-owner="exam.doctor === user?.id"
        @complete="onComplete"
        @confirm="onConfirm"
        @delete="onDelete"
        @revert="onRevert"
      />

      <div class="mt-4 flex gap-2">
        <Button
          label="Lưu kết luận"
          icon="pi pi-save"
          :loading="savingMeta"
          :disabled="!isDoctor()"
          @click="onSaveConclusion"
        />
        <Button label="Hủy" severity="secondary" outlined @click="goBack" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import Message from 'primevue/message'
import PageHeader from '@/components/common/PageHeader.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import DynamicExamForm from '@/components/examinations/DynamicExamForm.vue'
import ConclusionSection from '@/components/examinations/ConclusionSection.vue'
import ExamStatusActions from '@/components/examinations/ExamStatusActions.vue'
import { useExamStore } from '@/stores/exams'
import { useAuth } from '@/composables/useAuth'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { extractError } from '@/services/api'
import { flushPendingInputs } from '@/utils/flushPendingInputs'
import { evaluateComputedFields } from '@/utils/formula'
import type { FormDepartment, WorkFitness } from '@/types'

const route = useRoute()
const router = useRouter()
const store = useExamStore()
const { user, isRole } = useAuth()
const toast = useToast()
const confirm = useConfirm()

const examId = route.params.id as string
const exam = computed(() => store.current)
const formData = computed(() => store.formData)

const dirtyTabs = ref<Set<string>>(new Set())
const savingDept = ref<string | null>(null)
const savingMeta = ref(false)
const saveError = ref('')

const localConclusion = ref('')
const localConsultation = ref('')
const localWorkFitness = ref<WorkFitness>('pending')
const localClassification = ref<number | null>(null)
const localDisease = ref('')

const editableDepartments = computed<FormDepartment[]>(() => {
  if (!formData.value) return []
  return formData.value.departments.map((d) => {
    const role = user.value?.role
    let editable = false
    if (role === 'admin' || role === 'doctor') editable = true
    else if (role === 'nurse') editable = d.department.category === 'clinical'
    else if (role === 'labtech') editable = d.department.category === 'para_clinical'
    return { ...d, editable }
  })
})

function isDoctor() {
  return isRole('admin', 'doctor')
}

function onUpdateData(departmentId: string, key: string, value: unknown) {
  dirtyTabs.value.add(departmentId)
  // Update actual data in store so save emits correct values
  if (store.formData) {
    const dept = store.formData.departments.find((d) => d.result_id === departmentId)
    if (dept) {
      dept.data[key] = value
    }
  }
}

async function onSaveDept(departmentId: string, data: Record<string, unknown>) {
  savingDept.value = departmentId
  try {
    await flushPendingInputs()
    const dept = store.formData?.departments.find((d) => d.result_id === departmentId)
    if (dept) {
      dept.data = evaluateComputedFields(
        dept.template_snapshot,
        dept.data,
        formData.value?.patient_gender ?? null,
      )
    }
    const payload = dept?.data ?? data
    console.log('[EditPage] Saving dept:', departmentId, 'data:', JSON.stringify(payload))
    await store.saveDepartmentResult(examId, departmentId, payload)
    dirtyTabs.value.delete(departmentId)
    toast.showSuccess('Đã lưu kết quả')
    await store.fetchForm(examId)
    console.log('[EditPage] After reload, form data:', store.formData?.departments.map(d => ({ id: d.result_id, data: d.data })))
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi khi lưu'))
  } finally {
    savingDept.value = null
  }
}

async function onSaveConclusion() {
  if (!exam.value) return
  savingMeta.value = true
  saveError.value = ''
  try {
    const payload = {
      ...exam.value,
      consultation: localConsultation.value,
      conclusion: localConclusion.value,
      work_fitness: localWorkFitness.value,
      classification: localClassification.value,
      disease: localDisease.value,
    }
    await store.update(examId, payload)
    toast.showSuccess('Đã lưu kết luận')
  } catch (err) {
    saveError.value = extractError(err, 'Lỗi khi lưu kết luận')
  } finally {
    savingMeta.value = false
  }
}

async function onComplete() {
  const ok = await confirm.require('Hoàn thành lượt khám', 'Xác nhận hoàn thành?')
  if (!ok) return
  try {
    await store.updateStatus(examId, 'completed')
    toast.showSuccess('Đã hoàn thành')
    await loadData()
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi'))
  }
}

async function onConfirm() {
  const ok = await confirm.require('Xác nhận', 'Xác nhận chính thức? Sau đó sẽ không thể sửa.')
  if (!ok) return
  try {
    await store.updateStatus(examId, 'confirmed')
    toast.showSuccess('Đã xác nhận')
    await loadData()
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi'))
  }
}

async function onDelete() {
  const ok = await confirm.require('Xóa', 'Xóa lượt khám?', true)
  if (!ok) return
  try {
    await store.remove(examId)
    toast.showSuccess('Đã xóa')
    router.push({ name: 'exam-list' })
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi'))
  }
}

async function onRevert() {
  const ok = await confirm.require('Hoàn tác', 'Đưa về nháp?')
  if (!ok) return
  try {
    await store.updateStatus(examId, 'draft')
    toast.showSuccess('Đã hoàn tác')
    await loadData()
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi'))
  }
}

function goBack() {
  router.push({ name: 'exam-detail', params: { id: examId } })
}

async function loadData() {
  await store.fetchById(examId)
  try {
    await store.fetchForm(examId)
    if (exam.value) {
      localConclusion.value = exam.value.conclusion
      localConsultation.value = exam.value.consultation
      localWorkFitness.value = exam.value.work_fitness ?? 'pending'
      localClassification.value = exam.value.classification ?? null
      localDisease.value = exam.value.disease ?? ''
    }
  } catch {
    // form endpoint may not be available yet
  }
}

onMounted(loadData)
</script>
