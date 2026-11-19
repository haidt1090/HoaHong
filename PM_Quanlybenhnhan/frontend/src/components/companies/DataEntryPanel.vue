<template>
  <div>
    <div class="mb-3 flex items-center justify-end">
      <Button
        label="Phím tắt"
        icon="pi pi-keyboard"
        size="small"
        severity="secondary"
        outlined
        @click="shortcutsVisible = true"
      />
    </div>

    <div v-if="!employeeId" class="py-8 text-center text-text-muted">
      <i class="pi pi-search text-3xl" />
      <p class="mt-2">Chọn nhân viên để bắt đầu nhập liệu</p>
    </div>

    <div v-else-if="!packageIds.length" class="py-8 text-center text-text-muted">
      <i class="pi pi-box text-3xl" />
      <p class="mt-2">Chọn ít nhất một gói khám</p>
    </div>

    <template v-else>
      <div class="mb-3 flex items-center justify-between text-sm text-text-body">
        <span>Đã chọn: <strong class="text-primary">{{ employeeName }}</strong></span>
        <span v-if="dirtyCount > 0" class="text-xs font-medium text-warning">
          {{ dirtyCount }} phòng chưa lưu
        </span>
      </div>

      <div v-for="block in blocks" :key="block.companyExamPackageId" class="mb-6">
        <LoadingSkeleton v-if="block.loading" type="card" :rows="2" />

        <template v-else>
          <!-- Package header with department chips -->
          <div class="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2">
            <h4 class="mr-2 text-sm font-semibold text-text-body">{{ block.packageName }}</h4>
            <StatusBadge :status="block.overallStatus" size="sm" />
            <span class="mx-1 text-gray-300">|</span>
            <template v-if="block.departments.length === 0">
              <span class="text-xs text-text-muted">Chưa có phòng ban</span>
            </template>
            <button
              v-for="dept in block.departments"
              :key="dept.key"
              type="button"
              class="flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition-colors"
              :style="chipStyle(block.companyExamPackageId, dept)"
              @click="toggleDept(block.companyExamPackageId, dept.key)"
            >
              {{ dept.departmentName }}
              <span v-if="dept.completed" class="text-[10px] opacity-70">{{ dept.dirty ? '(chỉnh sửa)' : '(đã xong)' }}</span>
              <span v-else-if="dept.dirty" class="text-[10px] opacity-70">(chưa lưu)</span>
              <span v-else class="text-[10px] opacity-50">(chưa khám)</span>
            </button>
          </div>

          <!-- Expanded department spreadsheets -->
          <template v-for="dept in block.departments" :key="dept.key">
            <div
              v-if="isDeptExpanded(block.companyExamPackageId, dept.key)"
              :id="'dept-' + deptId(block.companyExamPackageId, dept.key)"
              class="mb-4 rounded-lg border border-gray-200"
              @focusin="onDeptFocus(block.companyExamPackageId, dept.key)"
              @keydown.enter="onDeptEnter($event, block.companyExamPackageId, dept.key)"
            >
              <div class="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-3 py-1.5">
                <span class="text-xs font-semibold text-text-body">{{ dept.departmentName }}</span>
                <button
                  type="button"
                  class="text-xs text-text-muted hover:text-danger"
                  @click="toggleDept(block.companyExamPackageId, dept.key)"
                >
                  <i class="pi pi-times" />
                </button>
              </div>

              <div v-if="dept.fields.length === 0" class="py-4 text-center text-sm text-text-muted">
                Chưa có chỉ số
              </div>
              <SpreadsheetTable
                v-else
                :key="`${employeeId}-${dept.key}`"
                :fields="dept.fields"
                :model-value="dept.data"
                :gender="employeeGender"
                @update:model-value="(key: string, value: unknown) => onFieldChange(block.companyExamPackageId, dept.key, key, value)"
              />

              <div class="flex justify-end gap-2 border-t border-gray-100 px-3 py-2">
                <Button
                  label="Xoá dữ liệu"
                  size="small"
                  severity="secondary"
                  text
                  @click="onClear(block.companyExamPackageId, dept.key)"
                />
                <Button
                  v-tooltip.top="'Lưu (Ctrl+S)'"
                  label="Lưu"
                  size="small"
                  icon="pi pi-save"
                  :loading="dept.saving"
                  @click="onSaveDept(block.companyExamPackageId, dept.key)"
                />
              </div>
            </div>
          </template>

          <div v-if="block.departments.length > 0" class="flex justify-end gap-2">
            <Button
              v-tooltip.top="'Lưu tất cả rồi sang NV kế (Ctrl+Shift+S)'"
              label="Lưu tất cả"
              icon="pi pi-save"
              severity="secondary"
              outlined
              size="small"
              :loading="savingAll"
              @click="onSaveAll"
            />
          </div>
        </template>
      </div>
    </template>

    <ShortcutsModal v-model:visible="shortcutsVisible" :groups="DATA_ENTRY_SHORTCUTS" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick } from 'vue'
import Button from 'primevue/button'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import SpreadsheetTable from '@/components/companies/SpreadsheetTable.vue'
import { packagesService } from '@/services/packages'
import { examsService } from '@/services/exams'
import { patientsService } from '@/services/patients'
import { useToast } from '@/composables/useToast'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'
import { extractError } from '@/services/api'
import { resolveSeedValue, isComputedField, shouldSeedField } from '@/utils/field'
import { flushPendingInputs } from '@/utils/flushPendingInputs'
import { evaluateComputedFields } from '@/utils/formula'
import ShortcutsModal from '@/components/common/ShortcutsModal.vue'
import { DATA_ENTRY_SHORTCUTS, SHORTCUT_CONFIG } from '@/shortcuts'
import type {
  FieldDefinition,
  ExamFormData,
  CompanyExamPackage,
  Patient,
  Gender,
} from '@/types'

interface DeptBlock {
  key: string
  templateId?: string | null
  deptResultId: string | null
  departmentName: string
  departmentId?: string | null
  fields: FieldDefinition[]
  data: Record<string, unknown>
  originalData: string
  completed: boolean
  dirty: boolean
  saving: boolean
}

interface PackageBlock {
  companyExamPackageId: string
  examPackageId: string
  packageName: string
  examId: string | null
  overallStatus: string
  loading: boolean
  departments: DeptBlock[]
}

type RawExamRow = {
  id: string
  status: string
  exam_package?: string | null
  company_exam_package?: string | null
}

const props = defineProps<{
  companyId: string
  employeeId: string | null
  packageIds: string[]
  active?: boolean
}>()

const emit = defineEmits<{
  saved: []
  'select-employee': [patient: Patient]
  'focus-search': []
}>()

type FormDeptRow = {
  department: { id: string }
  template_id?: string | null
  result_id: string
  data?: Record<string, unknown>
  completed?: boolean
  fields_table?: Array<{ key?: string; value?: unknown }>
}

function sameId(a: unknown, b: unknown): boolean {
  if (a == null || b == null || a === '' || b === '') return false
  return String(a) === String(b)
}

function matchFormDepartment(
  formData: ExamFormData | null | undefined,
  templateId: string | null | undefined,
  departmentId: string | null | undefined,
): FormDeptRow | undefined {
  const depts = (formData?.departments ?? []) as FormDeptRow[]
  if (!depts.length) return undefined
  const byTemplate = templateId
    ? depts.find((d) => sameId(d.template_id, templateId))
    : undefined
  if (byTemplate) return byTemplate
  return departmentId
    ? depts.find((d) => sameId(d.department?.id, departmentId))
    : undefined
}

function hasStoredValue(value: unknown): boolean {
  return value !== undefined && value !== null && value !== ''
}

function dataFromFormDept(fd: FormDeptRow): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const row of fd.fields_table ?? []) {
    if (row?.key && hasStoredValue(row.value)) out[row.key] = row.value
  }
  for (const [key, value] of Object.entries(fd.data ?? {})) {
    if (hasStoredValue(value)) out[key] = value
  }
  return out
}

function examListFromResponse(payload: unknown): RawExamRow[] {
  const body = (payload as { data?: unknown })?.data ?? payload
  if (Array.isArray(body)) return body as RawExamRow[]
  const results = (body as { results?: unknown })?.results
  return Array.isArray(results) ? (results as RawExamRow[]) : []
}

function findExistingExam(
  exams: RawExamRow[],
  companyExamPackageId: string,
  examPackageId: string,
): RawExamRow | undefined {
  return (
    exams.find((e) => sameId(e.company_exam_package, companyExamPackageId)) ??
    exams.find((e) => sameId(e.exam_package, examPackageId))
  )
}

function seedDeptData(
  fields: FieldDefinition[],
  fd: FormDeptRow | undefined,
  gender: Gender | null,
  allowRandom: boolean,
): { data: Record<string, unknown>; resultId: string | null; completed: boolean } {
  const data: Record<string, unknown> = fd ? dataFromFormDept(fd) : {}
  for (const field of fields) {
    if (isComputedField(field) || field.key in data) continue
    if (!shouldSeedField(field, gender)) continue
    if (allowRandom) {
      const seed = resolveSeedValue(field, gender)
      if (seed !== null && seed !== undefined) data[field.key] = seed
    } else if (field.default_value !== null && field.default_value !== undefined && field.default_value !== '') {
      data[field.key] = field.default_value
    }
  }
  return {
    data,
    resultId: fd?.result_id ?? null,
    completed: !!fd?.completed,
  }
}

let loadSeq = 0
const toast = useToast()
const blocks = ref<PackageBlock[]>([])
const employeeName = ref('')
const employeeGender = ref<Gender | null>(null)
const savingAll = ref(false)
const expandedDepts = ref<Set<string>>(new Set())
const companyPackagesCache = ref<CompanyExamPackage[]>([])
const shortcutsVisible = ref(false)
const currentDept = ref<{ pkgId: string; deptKey: string } | null>(null)
let suppressNextFocus = false
const templateCache = new Map<string, { fields: FieldDefinition[]; name: string }>()

const dirtyCount = computed(() => {
  let count = 0
  for (const block of blocks.value) {
    for (const dept of block.departments) {
      if (dept.dirty) count++
    }
  }
  return count
})

const allDepartments = computed(() => {
  const list: Array<{ pkgId: string; dept: DeptBlock }> = []
  for (const block of blocks.value) {
    for (const dept of block.departments) {
      list.push({ pkgId: block.companyExamPackageId, dept })
    }
  }
  return list
})

function getBlock(pkgId: string): PackageBlock | undefined {
  return blocks.value.find((b) => b.companyExamPackageId === pkgId)
}

function getDept(pkgId: string, deptKey: string): DeptBlock | undefined {
  return getBlock(pkgId)?.departments.find((d) => d.key === deptKey)
}

function deptId(pkgId: string, deptKey: string): string {
  return `${pkgId}:${deptKey}`
}

function expandedDeptsStorageKey(): string {
  return `data-entry-expanded-depts:${props.companyId}`
}

function readStoredExpandedDepts(): Set<string> {
  try {
    const raw = sessionStorage.getItem(expandedDeptsStorageKey())
    if (!raw) return new Set()
    const parsed: unknown = JSON.parse(raw)
    return new Set(Array.isArray(parsed) ? parsed.map(String) : [])
  } catch {
    return new Set()
  }
}

function persistExpandedDepts(ids: Set<string>): void {
  try {
    sessionStorage.setItem(expandedDeptsStorageKey(), JSON.stringify([...ids]))
  } catch {
    // Ignore quota / private-mode failures.
  }
}

function validExpandedIds(blocks: PackageBlock[]): Set<string> {
  const valid = new Set<string>()
  for (const block of blocks) {
    for (const dept of block.departments) {
      valid.add(deptId(block.companyExamPackageId, dept.key))
    }
  }
  return valid
}

/** Keep the user's open department chips; only default to the first khoa on first visit. */
function restoreExpandedDepts(blocks: PackageBlock[]): void {
  const valid = validExpandedIds(blocks)
  const current = new Set([...expandedDepts.value].filter((id) => valid.has(id)))
  const stored = [...readStoredExpandedDepts()].filter((id) => valid.has(id))
  const next = current.size > 0 ? current : new Set(stored)
  if (next.size === 0) {
    for (const block of blocks) {
      if (block.departments.length > 0) {
        next.add(deptId(block.companyExamPackageId, block.departments[0].key))
      }
    }
  }
  expandedDepts.value = next
  persistExpandedDepts(next)
}

function isDeptExpanded(pkgId: string, deptKey: string): boolean {
  return expandedDepts.value.has(deptId(pkgId, deptKey))
}

function focusFirstInput(): void {
  if (suppressNextFocus) {
    suppressNextFocus = false
    return
  }
  void nextTick(() => {
    for (const block of blocks.value) {
      for (const dept of block.departments) {
        if (!isDeptExpanded(block.companyExamPackageId, dept.key)) continue
        const wrapper = document.getElementById(
          `dept-${deptId(block.companyExamPackageId, dept.key)}`,
        )
        const input = wrapper?.querySelector(
          'input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled])',
        ) as HTMLElement | null
        if (input) {
          input.focus()
          return
        }
      }
    }
  })
}

function focusDeptInput(id: string): void {
  nextTick(() => {
    const wrapper = document.getElementById(`dept-${id}`)
    if (wrapper) {
      const input = wrapper.querySelector('input:not([type="hidden"]), select, textarea') as HTMLElement | null
      input?.focus()
    }
  })
}

function scrollToDept(id: string): void {
  nextTick(() => {
    document.getElementById(`dept-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

function onDeptFocus(pkgId: string, deptKey: string): void {
  currentDept.value = { pkgId, deptKey }
}

function onDeptEnter(event: KeyboardEvent, pkgId: string, deptKey: string): void {
  if (!SHORTCUT_CONFIG.autoSaveOnEnterLastCell) return
  const target = event.target as HTMLElement | null
  if (target?.closest('[data-field-last]')) {
    event.preventDefault()
    onSaveDept(pkgId, deptKey)
  }
}

function resolveCurrentDept(): { pkgId: string; deptKey: string } | null {
  if (currentDept.value && getDept(currentDept.value.pkgId, currentDept.value.deptKey)) {
    return currentDept.value
  }
  for (const block of blocks.value) {
    for (const dept of block.departments) {
      if (isDeptExpanded(block.companyExamPackageId, dept.key)) {
        return { pkgId: block.companyExamPackageId, deptKey: dept.key }
      }
    }
  }
  for (const block of blocks.value) {
    for (const dept of block.departments) {
      if (dept.dirty) return { pkgId: block.companyExamPackageId, deptKey: dept.key }
    }
  }
  return null
}

function saveCurrentDepartment(): void {
  const cur = resolveCurrentDept()
  if (cur) void onSaveDept(cur.pkgId, cur.deptKey)
}

function switchToDepartment(index: number): void {
  const target = allDepartments.value[index - 1]
  if (!target) return
  const id = deptId(target.pkgId, target.dept.key)
  const next = new Set(expandedDepts.value)
  next.add(id)
  expandedDepts.value = next
  persistExpandedDepts(next)
  currentDept.value = { pkgId: target.pkgId, deptKey: target.dept.key }
  scrollToDept(id)
  focusDeptInput(id)
}

async function navigateEmployee(
  direction: 1 | -1,
  options: { focusForm?: boolean } = {},
): Promise<void> {
  if (!props.employeeId) return
  try {
    const { data } = await patientsService.list({
      company: props.companyId,
      is_active: true,
      page_size: 1000,
      ordering: 'employee_code',
    })
    const list: Patient[] = Array.isArray(data.results) ? data.results : (data as unknown as Patient[])
    const idx = list.findIndex((p) => p.id === props.employeeId)
    if (idx === -1) return
    const target = list[idx + direction]
    if (target) {
      // loadAll focuses the first input of the first expanded khoa unless skipped.
      suppressNextFocus = !options.focusForm
      emit('select-employee', target)
    }
    if (!options.focusForm) emit('focus-search')
  } catch {
    toast.showError('Không thể điều hướng nhân viên')
  }
}

async function saveAndNextEmployee(): Promise<void> {
  await onSaveAll()
}

function chipStyle(pkgId: string, dept: DeptBlock): Record<string, string> {
  if (isDeptExpanded(pkgId, dept.key)) {
    return { borderColor: '#0a7c6e', background: '#0a7c6e', color: '#fff' }
  }
  if (dept.completed) {
    return { borderColor: '#27ae60', background: '#eafaf1', color: '#1e8449' }
  }
  if (dept.dirty) {
    return { borderColor: '#f39c12', background: '#fef9e7', color: '#b7950b' }
  }
  return {}
}

function toggleDept(pkgId: string, deptKey: string): void {
  const id = deptId(pkgId, deptKey)
  const next = new Set(expandedDepts.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  expandedDepts.value = next
  persistExpandedDepts(next)
  focusFirstInput()
}

watch(
  [() => props.employeeId, () => props.packageIds],
  ([newEmpId, newPkgIds], [oldEmpId, oldPkgIds]) => {
    if (!newEmpId || !newPkgIds.length) {
      loadSeq += 1
      blocks.value = []
      return
    }

    const packagesChanged = JSON.stringify(newPkgIds) !== JSON.stringify(oldPkgIds)
    const employeeChanged = newEmpId !== oldEmpId

    if (packagesChanged) templateCache.clear()

    if (employeeChanged && blocks.value.length && !packagesChanged) {
      for (const block of blocks.value) block.loading = true
    }

    if (packagesChanged || employeeChanged || !blocks.value.length) {
      void loadAll()
    }
  },
  { immediate: true, deep: true },
)

async function loadTemplate(templateId: string): Promise<{ fields: FieldDefinition[]; name: string }> {
  const cached = templateCache.get(templateId)
  if (cached) return cached
  const { data: tpl } = await packagesService.getTemplate(templateId)
  const parsed = {
    fields: Array.isArray(tpl.fields_config) ? tpl.fields_config.filter(Boolean) : [],
    name: tpl.name ?? '',
  }
  templateCache.set(templateId, parsed)
  return parsed
}

async function loadAll(): Promise<void> {
  const seq = ++loadSeq
  if (!props.employeeId || !props.packageIds.length) {
    blocks.value = []
    return
  }

  try {
    const { data: patient } = await patientsService.get(props.employeeId)
    employeeName.value = patient.full_name
    employeeGender.value = patient.gender ?? null
  } catch (err) {
    console.error('[DataEntryPanel] Failed to fetch patient:', err)
    employeeName.value = ''
    employeeGender.value = null
  }

  let existingExams: RawExamRow[]
  try {
    const { data: examPage } = await examsService.list({ patient: props.employeeId, page_size: 200 })
    existingExams = examListFromResponse(examPage)
  } catch (err) {
    console.error('[DataEntryPanel] Failed to fetch exams:', err)
    existingExams = []
  }

  // Load company packages
  let companyPackages: CompanyExamPackage[]
  try {
    const { data: cpData } = await packagesService.listCompanyPackages(props.companyId)
    if (Array.isArray(cpData)) {
      companyPackages = cpData as CompanyExamPackage[]
    } else {
      const paged = cpData as { results?: CompanyExamPackage[] }
      companyPackages = (paged.results ?? []).filter(Boolean)
    }
  } catch (err) {
    console.error('[DataEntryPanel] Failed to fetch company packages:', err)
    companyPackages = []
  }

  companyPackagesCache.value = companyPackages

  const newBlocks: PackageBlock[] = []

  for (const cpId of props.packageIds) {
    const cp = companyPackages.find((p: CompanyExamPackage) => p.id === cpId)
    if (!cp) {
      console.warn('[DataEntryPanel] Package not found in company packages:', cpId)
      continue
    }

    const departments: DeptBlock[] = []
    let examId: string | null = null
    let overallStatus = 'draft'

    try {
      const { data: pkg } = await packagesService.getExamPackage(cp.exam_package)
      const bindings = pkg.package_departments ?? []

      const existingExam = findExistingExam(existingExams, cpId, cp.exam_package)

      let formData: ExamFormData | null = null

      if (existingExam) {
        examId = existingExam.id
        overallStatus = existingExam.status
        try {
          const { data: raw } = await examsService.getForm(existingExam.id)
          formData = raw
        } catch (err) {
          console.error('[DataEntryPanel] Failed to fetch form data:', err)
        }
      }

      for (const binding of bindings) {
        const deptName = binding.department_detail?.name ?? ''
        const deptKey = binding.id
        let fields: FieldDefinition[] = []
        let data: Record<string, unknown> = {}
        let resultId: string | null = null
        let completed = false
        let templateName = ''

        // Each binding is isolated: one broken template must not stop the
        // bindings that come after it from being rendered.
        try {
          try {
            const tpl = await loadTemplate(binding.template)
            fields = tpl.fields
            templateName = tpl.name
          } catch (err) {
            console.error('[DataEntryPanel] Failed to fetch template', binding.template, ':', err)
          }

          const displayName = templateName
            ? `${deptName} (${templateName})`
            : deptName

          const fd = matchFormDepartment(formData, binding.template, binding.department)
          const seeded = seedDeptData(fields, fd, employeeGender.value, !formData || !!fd)
          data = seeded.data
          resultId = seeded.resultId
          completed = seeded.completed

          const originalData = JSON.stringify(data)
          departments.push({
            key: deptKey,
            templateId: binding.template,
            deptResultId: resultId,
            departmentName: displayName,
            departmentId: binding.department,
            fields,
            data,
            originalData,
            completed,
            dirty: false,
            saving: false,
          })
        } catch (err) {
          console.error(
            '[DataEntryPanel] Lỗi khi dựng khoa',
            deptName,
            'binding',
            binding.id,
            'template',
            binding.template,
            err,
          )
          // Still show the chip so the gap is visible in the UI instead of the
          // department silently disappearing from the package.
          departments.push({
            key: deptKey,
            templateId: binding.template,
            deptResultId: null,
            departmentName: deptName,
            departmentId: binding.department,
            fields: [],
            data: {},
            originalData: '{}',
            completed: false,
            dirty: false,
            saving: false,
          })
        }
      }
    } catch (err) {
      console.error('[DataEntryPanel] Failed to load package details:', err)
    }

    newBlocks.push({
      companyExamPackageId: cpId,
      examPackageId: cp.exam_package,
      packageName: cp.package_detail?.name || cp.exam_package || 'Gói khám',
      examId,
      overallStatus,
      loading: false,
      departments,
    })
  }

  if (seq !== loadSeq) return
  blocks.value = newBlocks
  restoreExpandedDepts(newBlocks)
  await nextTick()
  await nextTick()
  focusFirstInput()
}

function onFieldChange(pkgId: string, deptKey: string, fieldKey: string, value: unknown): void {
  const dept = getDept(pkgId, deptKey)
  if (!dept) return
  dept.data = { ...dept.data, [fieldKey]: value }
  dept.dirty = JSON.stringify(dept.data) !== dept.originalData
}

function onClear(pkgId: string, deptKey: string): void {
  const dept = getDept(pkgId, deptKey)
  if (!dept) return
  dept.data = {}
  dept.dirty = JSON.stringify(dept.data) !== dept.originalData
}

async function onSaveDept(pkgId: string, deptKey: string): Promise<boolean> {
  // InputNumber only commits on blur; Ctrl+S / Enter-save skip that.
  await flushPendingInputs()
  const block = getBlock(pkgId)
  const dept = getDept(pkgId, deptKey)
  if (!block || !dept) return false

  dept.data = evaluateComputedFields(dept.fields, dept.data, employeeGender.value)

  dept.saving = true
  try {
    await ensureExam(block)
    if (!block.examId) throw new Error('Không thể tạo lượt khám')

    if (!dept.deptResultId) {
      // New binding added after exam creation — use department ID as fallback,
      // backend will auto-create DepartmentResult.
      if (!dept.departmentId) throw new Error('Không tìm thấy khoa')
      dept.deptResultId = dept.departmentId
    }
    const { data: result } = await examsService.updateDepartmentResult(block.examId, dept.deptResultId, { data: dept.data })
    dept.deptResultId = result.id
    dept.data = { ...result.data }
    const allFilled = dept.fields
      .filter((f) => f.required)
      .every((f) => dept.data[f.key] !== undefined && dept.data[f.key] !== null && dept.data[f.key] !== '')
    if (allFilled && !dept.completed) {
      await examsService.completeDepartmentResult(block.examId, dept.deptResultId)
      dept.completed = true
    }

    dept.originalData = JSON.stringify(dept.data)
    dept.dirty = false
    toast.showSuccess(`Đã lưu ${dept.departmentName}`)
    return true
  } catch (err) {
    toast.showError(extractError(err, `Lỗi khi lưu ${dept.departmentName}`))
    return false
  } finally {
    dept.saving = false
  }
}

async function onSaveAll(): Promise<void> {
  savingAll.value = true
  try {
    for (const block of blocks.value) {
      for (const dept of block.departments) {
        if (dept.dirty) {
          await onSaveDept(block.companyExamPackageId, dept.key)
        }
      }
    }
    toast.showSuccess(`Đã lưu kết quả cho ${employeeName.value}`)
    await navigateEmployee(1, { focusForm: true })
  } catch {
    // errors already shown by onSaveDept
  } finally {
    savingAll.value = false
  }
}

async function ensureExam(block: PackageBlock): Promise<void> {
  if (block.examId) return

  const now = new Date().toISOString().split('T')[0]
  const { data: exam } = await examsService.create({
    patient: props.employeeId!,
    company_exam_package: block.companyExamPackageId,
    exam_type: 'periodic',
    exam_date: now,
  })
  block.examId = exam.id
  block.overallStatus = 'draft'

  // Fetch form to get actual DepartmentResult IDs
  try {
    const { data: raw } = await examsService.getForm(exam.id)
    for (const dept of block.departments) {
      const fd = (raw.departments as Array<{ template_id: string | null; result_id: string; department: { id: string } }>)
        .find((d) => d.template_id === String(dept.templateId))
        ?? (raw.departments as Array<{ template_id: string | null; result_id: string; department: { id: string } }>)
        .find((d) => d.template_id === null && d.department.id === String(dept.departmentId))
      if (fd) {
        dept.deptResultId = fd.result_id
      }
    }
  } catch (err) {
    console.error('[DataEntryPanel] Failed to fetch form after exam creation:', err)
  }
}

const shortcuts = useKeyboardShortcuts()
const isActive = () => props.active !== false

shortcuts.register('Ctrl+S', () => saveCurrentDepartment(), { preventDefault: true, when: isActive })
shortcuts.register('Ctrl+Shift+S', () => onSaveAll(), { preventDefault: true, when: isActive })
shortcuts.register('Ctrl+Q', () => saveAndNextEmployee(), { preventDefault: true, when: isActive })
shortcuts.register('Ctrl+Shift+Q', () => navigateEmployee(-1), { preventDefault: true, when: isActive })
for (let i = 1; i <= 9; i++) {
  shortcuts.register(`Ctrl+${i}`, () => switchToDepartment(i), { preventDefault: true, when: isActive })
}
</script>
