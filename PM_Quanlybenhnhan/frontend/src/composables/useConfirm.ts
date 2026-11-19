import { useConfirm as usePrimeConfirm } from 'primevue/useconfirm'

/** Confirm dialog helper returning a Promise<boolean>. */
export function useConfirm() {
  const confirm = usePrimeConfirm()

  function require(title: string, message: string, danger = false): Promise<boolean> {
    return new Promise((resolve) => {
      confirm.require({
        header: title,
        message,
        icon: 'pi pi-exclamation-triangle',
        rejectLabel: 'Hủy',
        acceptLabel: 'Đồng ý',
        acceptClass: danger ? 'p-button-danger' : undefined,
        accept: () => resolve(true),
        reject: () => resolve(false),
        onHide: () => resolve(false),
      })
    })
  }

  return { require }
}
