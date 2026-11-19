<template>
  <div class="mt-4 rounded-lg border border-gray-200 bg-white p-4">
    <h4 class="mb-3 text-base font-semibold text-text-body">Kết luận & Tư vấn</h4>
    <div class="flex flex-col gap-3">
      <div class="flex items-end gap-3">
        <div class="flex-1">
          <label class="mb-1 block text-sm font-medium text-text-body">Bệnh mắc</label>
          <InputText
            :model-value="disease"
            :disabled="!editable"
            placeholder="Tự động điền từ chẩn đoán..."
            fluid
            @update:model-value="onDiseaseChange"
          />
        </div>
        <Button
          label="Gợi ý chẩn đoán"
          icon="pi pi-lightbulb"
          severity="info"
          outlined
          :disabled="suggesting"
          :loading="suggesting"
          @click="onSuggest"
        />
      </div>

      <!-- Diagnosis suggestions from server API -->
      <div v-if="diagnosisResults.length" class="rounded border border-blue-200 bg-blue-50 p-3">
        <p class="mb-2 text-sm font-medium text-blue-800">
          Kết quả chẩn đoán từ dữ liệu khám:
        </p>
        <!-- Unfit warning banner -->
        <div
          v-if="hasUnfitResult"
          class="mb-2 rounded border border-red-300 bg-red-50 p-2"
        >
          <p class="text-sm font-semibold text-red-700">
            ⚠ Không đủ điều kiện lao động
          </p>
        </div>
        <div
          v-for="(d, idx) in diagnosisResults"
          :key="idx"
          class="mb-2 flex items-start gap-2 rounded border border-blue-100 bg-white p-2 last:mb-0"
          :class="{ 'border-red-200': d.classification !== null && d.classification >= DiagnosisClassification.POOR }"
        >
          <div class="flex-1">
            <p class="text-sm font-semibold text-text-body">
              {{ d.disease_name }}
              <span class="ml-1 text-xs text-blue-600">({{ d.keyword }})</span>
              <Tag
                v-if="d.classification === DiagnosisClassification.UNFIT"
                value="Loại 5"
                severity="danger"
                class="ml-1"
              />
              <Tag
                v-else-if="d.classification === DiagnosisClassification.POOR"
                value="Loại 4"
                severity="danger"
                class="ml-1"
              />
              <Tag
                v-else-if="d.classification"
                :value="`Loại ${d.classification}`"
                severity="info"
                class="ml-1"
              />
            </p>
            <p class="text-xs text-text-secondary">{{ d.conclusion_template }}</p>
          </div>
          <Button
            v-if="editable"
            icon="pi pi-check"
            size="small"
            severity="success"
            text
            rounded
            title="Áp dụng tư vấn"
            @click="applyDiagnosis(d)"
          />
        </div>
      </div>

      <!-- Tư vấn (consultation) -->
      <div>
        <label class="mb-1 block text-sm font-medium text-text-body">Tư vấn</label>
        <Textarea
          :model-value="consultation"
          :disabled="!editable"
          rows="4"
          placeholder="Tư vấn từ kết quả chẩn đoán..."
          fluid
          @update:model-value="onConsultationChange"
        />
      </div>

      <!-- Kết luận: đủ / không đủ điều kiện lao động -->
      <div>
        <label class="mb-1 block text-sm font-medium text-text-body">
          Kết luận (điều kiện lao động)
        </label>
        <Select
          :model-value="workFitness"
          :options="workFitnessOptions"
          option-label="label"
          option-value="value"
          :disabled="!editable"
          placeholder="-- Chọn kết luận --"
          fluid
          @update:model-value="onWorkFitnessChange"
        />
        <p
          v-if="workFitness === 'unfit'"
          class="mt-1 text-xs font-medium text-red-600"
        >
          ⚠ Không đủ điều kiện lao động
        </p>
      </div>

      <!-- Phân loại sức khỏe (classification) -->
      <div>
        <label class="mb-1 block text-sm font-medium text-text-body">
          Phân loại sức khỏe
        </label>
        <Select
          :model-value="classification"
          :options="classificationOptions"
          option-label="label"
          option-value="value"
          :disabled="!editable"
          placeholder="-- Chọn phân loại --"
          show-clear
          fluid
          @update:model-value="onClassificationChange"
        />
      </div>

      <!-- Kết luận chi tiết (ghi chú tự do) -->
      <div>
        <label class="mb-1 block text-sm font-medium text-text-body">Ghi chú kết luận</label>
        <Textarea
          :model-value="conclusion"
          :disabled="!editable"
          rows="3"
          placeholder="Ghi chú thêm của bác sĩ..."
          fluid
          @update:model-value="onConclusionChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Textarea from 'primevue/textarea'
import Tag from 'primevue/tag'
import { diagnosisService } from '@/services/diagnosis'
import { extractError } from '@/services/api'
import { useToast } from '@/composables/useToast'
import { DiagnosisClassification } from '@/types'
import type { DiagnosisMatch, WorkFitness } from '@/types'

const workFitnessOptions = [
  { label: 'Chưa kết luận', value: 'pending' as WorkFitness },
  { label: 'Đủ điều kiện lao động', value: 'fit' as WorkFitness },
  { label: 'Không đủ điều kiện lao động', value: 'unfit' as WorkFitness },
]

const classificationOptions = [
  { label: '1', value: 1 },
  { label: '2', value: 2 },
  { label: '3', value: 3 },
  { label: '4', value: 4 },
  { label: '5', value: 5 },
]

const props = defineProps<{
  conclusion: string
  consultation: string
  disease: string
  workFitness: WorkFitness
  classification: number | null
  examId?: string
  editable: boolean
}>()

const emit = defineEmits<{
  'update:conclusion': [value: string]
  'update:consultation': [value: string]
  'update:disease': [value: string]
  'update:workFitness': [value: WorkFitness]
  'update:classification': [value: number | null]
}>()

const toast = useToast()

const suggesting = ref(false)
const diagnosisResults = ref<DiagnosisMatch[]>([])

const hasUnfitResult = computed(() =>
  diagnosisResults.value.some(
    (d) => d.classification !== null && d.classification >= DiagnosisClassification.POOR,
  ),
)

function onConclusionChange(value: string) {
  emit('update:conclusion', value)
}

function onConsultationChange(value: string) {
  emit('update:consultation', value)
}

function onDiseaseChange(value: string | undefined) {
  emit('update:disease', value ?? '')
}

function onWorkFitnessChange(value: WorkFitness) {
  emit('update:workFitness', value)
}

function onClassificationChange(value: number | null) {
  emit('update:classification', value ?? null)
}

function applyDiagnosis(diag: DiagnosisMatch) {
  // Append conclusion_template to consultation
  const current = (props.consultation || '').trim()
  const template = diag.conclusion_template.trim()
  if (template && !current.includes(template)) {
    emit('update:consultation', current ? `${current}, ${template}` : template)
  }
}

async function onSuggest() {
  if (!props.examId) {
    toast.showWarn('Không có thông tin lượt khám để gợi ý')
    return
  }
  suggesting.value = true
  diagnosisResults.value = []
  try {
    const { data } = await diagnosisService.getDiagnosis(props.examId)
    diagnosisResults.value = data.matches
    if (!data.matches.length) {
      toast.showInfo('Không tìm thấy chẩn đoán nào khớp với dữ liệu khám')
    }
    // Auto-default work_fitness to 'unfit' when any match has classification>=4
    // (doctor can still override)
    const hasUnfit = data.matches.some(
      (d) => d.classification !== null && d.classification >= DiagnosisClassification.POOR,
    )
    if (hasUnfit) {
      emit('update:workFitness', 'unfit')
    }
    // Auto-fill classification from the summary classification.
    if (data.classification !== null) {
      emit('update:classification', data.classification)
    }
    // Auto-fill disease from matched disease names.
    const names = data.matches
      .map((d) => d.disease_name.trim())
      .filter(Boolean)
    if (names.length && !(props.disease || '').trim()) {
      emit('update:disease', names.join(', '))
    }
    // Auto-fill consultation from all matched conclusion templates
    const templates = data.matches
      .map((d) => d.conclusion_template.trim())
      .filter(Boolean)
    if (templates.length && !(props.consultation || '').trim()) {
      emit('update:consultation', templates.join(', '))
    }
  } catch (err) {
    toast.showError(extractError(err, 'Lỗi khi tìm chẩn đoán'))
  } finally {
    suggesting.value = false
  }
}
</script>
