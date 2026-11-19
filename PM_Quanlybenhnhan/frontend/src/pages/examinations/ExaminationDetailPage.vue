<template>
  <div>
    <PageHeader :title="exam ? `Khám — ${exam.patient_name ?? exam.patient}` : 'Chi tiết lượt khám'">
      <template #actions>
        <Button
          v-if="exam && exam.status === 'draft' && canEdit"
          label="Sửa"
          icon="pi pi-pencil"
          severity="secondary"
          @click="router.push({ name: 'exam-edit', params: { id: exam.id } })"
        />
        <Button
          v-if="exam"
          label="In sổ"
          icon="pi pi-print"
          severity="secondary"
          outlined
          @click="print"
        />
      </template>
    </PageHeader>

    <LoadingSkeleton v-if="store.loading" type="card" :rows="4" />

    <template v-else-if="exam">
      <SectionCard title="Thông tin chung" icon="pi pi-info-circle">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <InfoRow label="Bệnh nhân" :value="exam.patient_name ?? exam.patient" />
          <InfoRow label="Loại khám" :value="examTypeLabel(exam.exam_type)" />
          <InfoRow label="Ngày khám" :value="exam.exam_date" />
          <InfoRow label="Bác sĩ" :value="exam.doctor_name || '--'" />
          <InfoRow label="Trạng thái">
            <StatusBadge :status="exam.status" size="sm" />
          </InfoRow>
          <InfoRow label="Bệnh mắc" :value="exam.disease || '--'" />
          <InfoRow label="Kết luận ĐK lao động" :value="workFitnessLabel" />
        </div>
      </SectionCard>

      <SectionCard title="Kết quả các phòng" icon="pi pi-list" class="mt-4">
        <DynamicExamForm
          v-if="formData"
          :departments="formData.departments"
          :dirty-tabs="null"
          :saving-dept="null"
          :patient-gender="formData.patient_gender ?? null"
          readonly
          @save-dept="() => {}"
          @update-data="() => {}"
        />
        <EmptyState
          v-else
          icon="pi pi-inbox"
          title="Chưa có dữ liệu phòng"
          description="Dữ liệu sẽ hiển thị sau khi nhập kết quả."
        />
      </SectionCard>

      <ConclusionSection
        v-if="exam"
        :consultation="exam.consultation ?? ''"
        :conclusion="exam.conclusion"
        :work-fitness="exam.work_fitness ?? 'pending'"
        :classification="exam.classification ?? null"
        :disease="exam.disease ?? ''"
        :exam-id="exam.id"
        :editable="false"
        @update:work-fitness="() => {}"
        @update:classification="() => {}"
        @update:disease="() => {}"
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
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import InfoRow from '@/components/common/InfoRow.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import DynamicExamForm from '@/components/examinations/DynamicExamForm.vue'
import ConclusionSection from '@/components/examinations/ConclusionSection.vue'
import ExamStatusActions from '@/components/examinations/ExamStatusActions.vue'
import { useExamStore } from '@/stores/exams'
import { useAuth } from '@/composables/useAuth'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { extractError } from '@/services/api'
import { examTypeLabel } from '@/utils/format'
import type { ExamFormData } from '@/types'

const route = useRoute()
const router = useRouter()
const store = useExamStore()
const { user, isRole } = useAuth()
const toast = useToast()
const confirm = useConfirm()

const examId = route.params.id as string
const exam = computed(() => store.current)
const formData = ref<ExamFormData | null>(null)

const canEdit = computed(() => {
  return isRole('admin', 'doctor', 'nurse', 'labtech')
})

const workFitnessLabels: Record<string, string> = {
  fit: 'Đủ điều kiện lao động',
  unfit: 'Không đủ điều kiện lao động',
}

const workFitnessLabel = computed(() => {
  const wf = exam.value?.work_fitness
  if (!wf || wf === 'pending') return '--'
  return workFitnessLabels[wf] ?? wf
})

async function loadData() {
  await store.fetchById(examId)
  try {
    formData.value = await store.fetchForm(examId)
  } catch {
    formData.value = null
  }
}

async function onComplete() {
  const ok = await confirm.require('Hoàn thành lượt khám', 'Xác nhận hoàn thành lượt khám này?')
  if (!ok) return
  try {
    await store.updateStatus(examId, 'completed')
    toast.showSuccess('Đã hoàn thành lượt khám')
    await loadData()
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi khi hoàn thành'))
  }
}

async function onConfirm() {
  const ok = await confirm.require('Xác nhận lượt khám', 'Xác nhận chính thức lượt khám này? Sau khi xác nhận sẽ không thể sửa.')
  if (!ok) return
  try {
    await store.updateStatus(examId, 'confirmed')
    toast.showSuccess('Đã xác nhận lượt khám')
    await loadData()
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi khi xác nhận'))
  }
}

async function onDelete() {
  const ok = await confirm.require('Xóa lượt khám', 'Xóa lượt khám này? Hành động không thể hoàn tác.', true)
  if (!ok) return
  try {
    await store.remove(examId)
    toast.showSuccess('Đã xóa lượt khám')
    router.push({ name: 'exam-list' })
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi khi xóa'))
  }
}

async function onRevert() {
  const ok = await confirm.require('Về nháp', 'Chuyển lượt khám về trạng thái nháp? Dữ liệu các phòng sẽ được giữ nguyên.')
  if (!ok) return
  try {
    await store.updateStatus(examId, 'draft')
    toast.showSuccess('Đã chuyển về nháp')
    await loadData()
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi khi chuyển về nháp'))
  }
}

function print() {
  window.print()
}

onMounted(loadData)
</script>
