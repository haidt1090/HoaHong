import { useToast as usePrimeToast } from 'primevue/usetoast'

/** Toast helpers wrapping PrimeVue's useToast. */
export function useToast() {
  const toast = usePrimeToast()

  function showSuccess(detail: string, summary = 'Thành công'): void {
    toast.add({ severity: 'success', summary, detail, life: 3000 })
  }

  function showError(detail: string, summary = 'Lỗi'): void {
    toast.add({ severity: 'error', summary, detail, life: 5000 })
  }

  function showWarn(detail: string, summary = 'Cảnh báo'): void {
    toast.add({ severity: 'warn', summary, detail, life: 4000 })
  }

  function showInfo(detail: string, summary = 'Thông tin'): void {
    toast.add({ severity: 'info', summary, detail, life: 3000 })
  }

  return { showSuccess, showError, showWarn, showInfo }
}
