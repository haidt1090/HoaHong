import { computed, type Ref } from 'vue'
import type { CompanyExamPackage } from '@/types'

/**
 * Pricing computation for a company exam package.
 *
 * - package_total: grand_total = default_package_price × total_employees
 * - per_field:     grand_total already computed server-side (total_cost)
 */
export function usePricing(pkg: Ref<CompanyExamPackage | null>) {
  const costPerEmployee = computed(() => {
    const p = pkg.value
    if (!p) return 0
    if (p.total_employees > 0) return Math.round(p.total_cost / p.total_employees)
    return p.package_detail?.default_package_price ?? 0
  })

  const grandTotal = computed(() => pkg.value?.total_cost ?? 0)

  return { costPerEmployee, grandTotal }
}
