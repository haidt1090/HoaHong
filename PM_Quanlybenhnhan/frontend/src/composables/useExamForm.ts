import { ref, computed, type Ref } from 'vue'
import { examsService } from '@/services/exams'
import { useAuth } from '@/composables/useAuth'
import type { ExamFormData, FormDepartment } from '@/types'

/**
 * Composable to manage the dynamic examination form state.
 * Handles loading form data, tracking dirty tabs, saving and completing departments.
 */
export function useExamForm(examId: Ref<string>) {
  const form = ref<ExamFormData | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const dirtyTabs = ref<Set<string>>(new Set())

  const { user } = useAuth()

  /** Load form data from the API */
  async function load(): Promise<void> {
    if (!examId.value) return
    loading.value = true
    try {
      const { data } = await examsService.getForm(examId.value)
      form.value = data
      dirtyTabs.value = new Set()
    } finally {
      loading.value = false
    }
  }

  /** Check if the current user can edit a given department */
  function canEditDepartment(dept: FormDepartment): boolean {
    if (!user.value) return false
    const role = user.value.role
    if (role === 'admin' || role === 'doctor') return true
    if (role === 'nurse') return dept.department.category === 'clinical'
    if (role === 'labtech') return dept.department.category === 'para_clinical'
    return false
  }

  /** The departments list with computed editable status */
  const departments = computed<FormDepartment[]>(() => {
    if (!form.value) return []
    return form.value.departments.map((dept) => ({
      ...dept,
      editable: dept.editable && canEditDepartment(dept),
    }))
  })

  /** Mark a tab as dirty (has unsaved changes) */
  function markDirty(departmentId: string): void {
    dirtyTabs.value.add(departmentId)
  }

  /** Save a single department's data */
  async function saveTab(
    departmentId: string,
    data: Record<string, unknown>,
  ): Promise<void> {
    saving.value = true
    try {
      await examsService.updateDepartmentResult(examId.value, departmentId, { data })
      dirtyTabs.value.delete(departmentId)
      // Refresh form data to get updated state
      await load()
    } finally {
      saving.value = false
    }
  }

  /** Complete (mark as done) a department result */
  async function completeTab(departmentId: string): Promise<void> {
    saving.value = true
    try {
      await examsService.completeDepartmentResult(examId.value, departmentId)
      await load()
    } finally {
      saving.value = false
    }
  }

  /** Number of completed departments */
  const completedCount = computed(() => {
    if (!form.value) return 0
    return form.value.departments.filter((d) => d.completed).length
  })

  /** Total number of departments */
  const totalCount = computed(() => {
    return form.value?.departments.length ?? 0
  })

  return {
    form,
    loading,
    saving,
    dirtyTabs,
    departments,
    completedCount,
    totalCount,
    load,
    markDirty,
    saveTab,
    completeTab,
    canEditDepartment,
  }
}
