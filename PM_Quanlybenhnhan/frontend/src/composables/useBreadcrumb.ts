import { computed } from 'vue'
import { useRoute } from 'vue-router'

export interface BreadcrumbItem {
  label: string
  to?: string
}

const SEGMENT_LABELS: Record<string, string> = {
  patients: 'Bệnh nhân',
  companies: 'Công ty',
  create: 'Thêm mới',
  edit: 'Chỉnh sửa',
  packages: 'Gói khám',
  sync: 'Đồng bộ CSDLKSK',
  mapping: 'Mapping XML',
  signatures: 'Chữ ký số',
  'usb-signer': 'Ký USB',
}

/** Build breadcrumb items from the current route path. */
export function useBreadcrumb() {
  const route = useRoute()

  const items = computed<BreadcrumbItem[]>(() => {
    const segments = route.path.split('/').filter(Boolean)
    const crumbs: BreadcrumbItem[] = [{ label: 'Tổng quan', to: '/' }]
    let path = ''
    for (const segment of segments) {
      path += `/${segment}`
      // Skip raw id segments (uuid-like) from labels
      const isId = /^[0-9a-f-]{20,}$/i.test(segment)
      crumbs.push({
        label: isId ? 'Chi tiết' : (SEGMENT_LABELS[segment] ?? segment),
        to: path,
      })
    }
    return crumbs
  })

  return { items }
}
