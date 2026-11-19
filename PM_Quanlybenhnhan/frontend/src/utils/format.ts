import type { ExamType, Gender } from '@/types'

export const EXAM_TYPE_LABELS: Record<ExamType, string> = {
  periodic: 'Khám định kỳ',
  occupational: 'Khám nghề nghiệp',
  job_placement: 'Khám bố trí nghề nghiệp',
  labor_under18: 'Khám lao động dưới 18',
  labor_over18: 'Khám lao động trên 18',
}

export const GENDER_LABELS: Record<Gender, string> = {
  M: 'Nam',
  F: 'Nữ',
}

export function examTypeLabel(type: string | null | undefined): string {
  if (!type) return '--'
  return EXAM_TYPE_LABELS[type as ExamType] ?? type
}

export function genderLabel(gender: string | null | undefined): string {
  if (!gender) return '--'
  return GENDER_LABELS[gender as Gender] ?? gender
}

export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return new Intl.NumberFormat('vi-VN').format(value) + ' đ'
}

/** Validate CCCD: 9 or 12 digits. Empty is allowed (optional field). */
export function isValidCccd(cccd: string): boolean {
  if (!cccd) return true
  return /^\d{9}$/.test(cccd) || /^\d{12}$/.test(cccd)
}
