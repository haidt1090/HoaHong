<template>
  <div>
    <LoadingSkeleton v-if="loading" type="form" :rows="6" />
    <template v-else-if="patient">
      <PageHeader :title="patient.full_name">
        <template #actions>
          <StatusBadge :status="patient.is_active ? 'active' : 'inactive'" />
          <Button
            v-if="isRole('admin', 'doctor', 'nurse')"
            label="Sửa"
            icon="pi pi-pencil"
            outlined
            @click="router.push({ name: 'patient-edit', params: { id: patient.id } })"
          />
          <Button
            v-if="isRole('admin')"
            label="Xóa"
            icon="pi pi-trash"
            severity="danger"
            outlined
            @click="handleDelete"
          />
        </template>
      </PageHeader>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <SectionCard title="Thông tin cá nhân" icon="pi pi-user">
          <dl class="m-0">
            <InfoRow label="Họ tên" :value="patient.full_name" />
            <InfoRow label="Ngày sinh" :value="patient.dob" />
            <InfoRow label="Giới tính" :value="genderLabel(patient.gender)" />
            <InfoRow label="CCCD/CMND" :value="patient.cccd" />
            <InfoRow label="Ngày cấp" :value="patient.cccd_issued_date" />
            <InfoRow label="Nơi cấp" :value="patient.cccd_issued_place" />
          </dl>
        </SectionCard>

        <SectionCard title="Công ty & Công việc" icon="pi pi-building">
          <dl class="m-0">
            <InfoRow label="Công ty" :value="patient.company_detail?.name || 'Cá nhân'" />
            <InfoRow label="Mã nhân viên" :value="patient.employee_code" />
            <InfoRow label="Phòng ban" :value="patient.department" />
            <InfoRow label="Ngày vào làm" :value="patient.start_date" />
          </dl>
        </SectionCard>

        <SectionCard title="Liên hệ" icon="pi pi-phone">
          <dl class="m-0">
            <InfoRow label="Địa chỉ" :value="patient.address" />
            <InfoRow label="Số điện thoại" :value="patient.phone" />
            <InfoRow label="Email" :value="patient.email" />
            <InfoRow label="Ghi chú" :value="patient.notes" />
          </dl>
        </SectionCard>
      </div>

      <SectionCard title="Lịch sử khám" icon="pi pi-history" class="mt-4">
        <ExaminationTimeline :items="patient.examinations || []" />
      </SectionCard>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Button from 'primevue/button'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import InfoRow from '@/components/common/InfoRow.vue'
import ExaminationTimeline from '@/components/patients/ExaminationTimeline.vue'
import { usePatientStore } from '@/stores/patients'
import { useAuth } from '@/composables/useAuth'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { genderLabel } from '@/utils/format'
import { extractError } from '@/services/api'

const router = useRouter()
const route = useRoute()
const store = usePatientStore()
const { isRole } = useAuth()
const toast = useToast()
const confirm = useConfirm()

const loading = ref(true)
const patient = computed(() => store.current)

async function handleDelete(): Promise<void> {
  const ok = await confirm.require('Xóa bệnh nhân', 'Bạn có chắc muốn xóa bệnh nhân này?', true)
  if (!ok) return
  try {
    await store.remove(route.params.id as string)
    toast.showSuccess('Đã xóa bệnh nhân')
    router.push({ name: 'patient-list' })
  } catch (err) {
    toast.showError(extractError(err, 'Không thể xóa bệnh nhân'))
  }
}

onMounted(async () => {
  await store.fetchById(route.params.id as string)
  loading.value = false
})
</script>
