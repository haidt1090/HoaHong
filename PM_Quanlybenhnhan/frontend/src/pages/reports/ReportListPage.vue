<template>
  <div>
    <PageHeader title="Báo cáo">
      <template #actions>
        <Button
          label="Tạo báo cáo"
          icon="pi pi-plus"
          @click="router.push({ name: 'report-generate' })"
        />
      </template>
    </PageHeader>

    <SectionCard>
      <div class="mb-4 flex flex-wrap items-center gap-3">
        <Select
          v-model="store.filters.report_type"
          :options="reportTypeOptions"
          option-label="label"
          option-value="value"
          placeholder="Tất cả loại báo cáo"
          show-clear
          class="w-full sm:w-64"
          @change="onFilterChange"
        />
      </div>

      <DataTable
        :columns="columns"
        :data="store.list"
        :loading="store.loading"
        paginator
        :rows="store.filters.page_size"
        :total-records="store.totalRecords"
        @page="onPage"
        @row-click="onRowClick"
      >
        <template #body-report_type="{ value }">
          {{ reportTypeLabel(value) }}
        </template>
        <template #body-output_format="{ value }">
          {{ value === 'xlsx' ? 'Excel' : 'HTML' }}
        </template>
        <template #body-status="{ value }">
          <StatusBadge :status="value" size="sm" />
        </template>
        <template #body-created_at="{ value }">
          {{ formatDate(value) }}
        </template>
        <template #actions="{ data }">
          <div class="flex gap-1">
            <Button
              v-if="data.status === 'done'"
              icon="pi pi-download"
              size="small"
              text
              rounded
              severity="info"
              aria-label="Tải về"
              @click.stop="downloadReport(data)"
            />
            <Button
              icon="pi pi-trash"
              size="small"
              text
              rounded
              severity="danger"
              aria-label="Xóa"
              @click.stop="deleteReport(data)"
            />
          </div>
        </template>
        <template #empty>
          <EmptyState
            icon="pi pi-file"
            title="Chưa có báo cáo"
            description="Tạo báo cáo đầu tiên cho công ty."
            action-label="Tạo báo cáo"
            @action="router.push({ name: 'report-generate' })"
          />
        </template>
      </DataTable>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Select from 'primevue/select'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useReportStore } from '@/stores/reports'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { reportsService } from '@/services/reports'
import { extractError } from '@/services/api'
import type { ColumnDef, Report, ReportType } from '@/types'

const router = useRouter()
const store = useReportStore()
const toast = useToast()
const confirm = useConfirm()

const REPORT_TYPE_LABELS: Record<ReportType, string> = {
  clinical_detail: 'Báo cáo chi tiết',
  company_summary: 'Báo cáo tổng hợp',
  occupational: 'Báo cáo bệnh nghề nghiệp',
  cost: 'Báo cáo chi phí',
}

const reportTypeOptions = [
  { label: 'Báo cáo chi tiết', value: 'clinical_detail' },
  { label: 'Báo cáo tổng hợp', value: 'company_summary' },
  { label: 'Báo cáo bệnh nghề nghiệp', value: 'occupational' },
  { label: 'Báo cáo chi phí', value: 'cost' },
]

const columns: ColumnDef[] = [
  { field: 'company_name', header: 'Công ty' },
  { field: 'exam_package_name', header: 'Gói khám' },
  { field: 'report_type', header: 'Loại báo cáo' },
  { field: 'output_format', header: 'Định dạng', width: '8rem' },
  { field: 'status', header: 'Trạng thái', width: '9rem' },
  { field: 'created_at', header: 'Ngày tạo', width: '10rem' },
]

function reportTypeLabel(type: string): string {
  return REPORT_TYPE_LABELS[type as ReportType] ?? type
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function onRowClick(row: unknown): void {
  const report = row as Report
  if (report.status === 'done') {
    downloadReport(report)
  }
}

async function downloadReport(report: Report): Promise<void> {
  try {
    const response = await reportsService.download(report.id)
    const blob = response.data as Blob
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const contentDisposition = response.headers['content-disposition'] as string | undefined
    let filename = ''
    if (contentDisposition) {
      // RFC 5987: filename*=UTF-8''encoded-name
      const rfc5987Match = contentDisposition.match(/filename\*=(?:UTF-8''|utf-8'')?([^;]*)/i)
      if (rfc5987Match) {
        filename = decodeURIComponent(rfc5987Match[1])
      } else {
        // Plain: filename="name" or filename=name
        const plainMatch = contentDisposition.match(/filename=["']?([^"';\n]*)["']?/)
        if (plainMatch) filename = plainMatch[1]
      }
    }
    if (!filename) {
      const ext = report.output_format === 'xlsx' ? 'xlsx' : 'html'
      filename = `${REPORT_TYPE_LABELS[report.report_type]}_${new Date().toISOString().slice(0, 10)}.${ext}`
    }
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    toast.showError(extractError(err, 'Không thể tải báo cáo'))
  }
}

async function deleteReport(report: Report): Promise<void> {
  const ok = await confirm.require(
    'Xóa báo cáo',
    `Xóa báo cáo "${reportTypeLabel(report.report_type)}"? Hành động này không thể hoàn tác.`,
    true,
  )
  if (!ok) return
  try {
    await store.remove(report.id)
    toast.showSuccess('Đã xóa báo cáo')
  } catch (err) {
    toast.showError(extractError(err, 'Không thể xóa báo cáo'))
  }
}

function onPage(event: unknown): void {
  const e = event as { page: number; rows: number }
  store.filters.page = e.page + 1
  store.filters.page_size = e.rows
  store.fetchList()
}

function onFilterChange(): void {
  store.filters.page = 1
  store.fetchList()
}

let pollTimer: ReturnType<typeof setInterval> | undefined

function startPolling(): void {
  stopPolling()
  pollTimer = setInterval(() => {
    const hasProcessing = store.list.some((r) => r.status === 'processing')
    if (hasProcessing) {
      store.fetchList()
    } else {
      stopPolling()
    }
  }, 5000)
}

function stopPolling(): void {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = undefined
  }
}

watch(
  () => store.list,
  () => {
    const hasProcessing = store.list.some((r) => r.status === 'processing')
    if (hasProcessing && !pollTimer) {
      startPolling()
    } else if (!hasProcessing) {
      stopPolling()
    }
  },
  { deep: true },
)

onMounted(async () => {
  await store.fetchList()
  if (store.list.some((r) => r.status === 'processing')) {
    startPolling()
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>
