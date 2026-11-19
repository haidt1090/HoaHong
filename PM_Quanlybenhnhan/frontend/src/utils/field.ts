import type { FieldDefinition, Gender, GenderOverride, NormalRange } from '@/types'

/**
 * Bounds are typed as numbers but arrive as strings from templates whose
 * gender overrides were entered in the Django admin. Coerce before any
 * arithmetic -- `"4.5" + 1` concatenates instead of adding.
 */
function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? n : null
}

export function baseNormalRange(field: FieldDefinition): NormalRange | undefined {
  const base = field.normal_range
  if (!base) return undefined
  const min = toNumber(base.min)
  const max = toNumber(base.max)
  if (min === null && max === null) return undefined
  return { min, max }
}

export function resolveNormalRange(
  field: FieldDefinition,
  gender: Gender | null | undefined,
): NormalRange | undefined {
  const override = gender ? field.gender_overrides?.[gender] : undefined
  if (override) {
    const min = toNumber(override.min)
    const max = toNumber(override.max)
    if (min !== null || max !== null) return { min, max }
  }
  const base = field.normal_range
  if (!base) return undefined
  return { min: toNumber(base.min), max: toNumber(base.max) }
}

export function resolveDefaultValue(
  field: FieldDefinition,
  _gender?: Gender | null,
): unknown {
  return field.default_value
}

/** Auto-calculated: type ``computed`` or any field that has a formula. */
export function isComputedField(
  field: Pick<FieldDefinition, 'type' | 'formula'>,
): boolean {
  return field.type === 'computed' || Boolean(field.formula?.trim())
}

export function fieldAppliesToGender(
  field: Pick<FieldDefinition, 'applies_to'>,
  gender: Gender | null | undefined,
): boolean {
  const applies = field.applies_to || 'all'
  if (!applies || applies === 'all') return true
  if (!gender) return true
  return gender === applies
}

export function shouldSeedField(
  field: Pick<FieldDefinition, 'applies_to'>,
  gender: Gender | null | undefined,
): boolean {
  const applies = field.applies_to || 'all'
  if (!applies || applies === 'all') return true
  if (!gender) return false
  return gender === applies
}

function resolveGenderOverride(
  field: FieldDefinition,
  gender: Gender | null | undefined,
): GenderOverride | undefined {
  return gender ? field.gender_overrides?.[gender] : undefined
}

/** Build discrete values ``min, min+step, …`` up to ``max`` (inclusive on-grid). */
export function buildStepGrid(min: number, max: number, step: number): number[] {
  if (!(step > 0) || max < min) return []
  const values: number[] = []
  // Integer math in fixed decimals avoids float drift (0.2 * n).
  const decimals = Math.max(
    (String(step).split('.')[1] || '').length,
    (String(min).split('.')[1] || '').length,
    (String(max).split('.')[1] || '').length,
  )
  const factor = 10 ** decimals
  const start = Math.round(min * factor)
  const end = Math.round(max * factor)
  const delta = Math.round(step * factor)
  if (delta <= 0) return []
  for (let cur = start; cur <= end; cur += delta) {
    values.push(cur / factor)
    if (values.length > 100_000) break
  }
  return values
}

export function resolveFieldForGender(
  field: FieldDefinition,
  gender: Gender | null | undefined,
): FieldDefinition {
  return {
    ...field,
    normal_range: resolveNormalRange(field, gender),
    default_value: resolveDefaultValue(field, gender),
  }
}

const DEFAULT_GENDER_OVERRIDE_STEP = 0.1

function randomInNormalRange(
  field: FieldDefinition,
  gender: Gender | null | undefined,
): number | null {
  if (field.type !== 'number') return null
  const range = resolveNormalRange(field, gender)
  if (!range) return null
  const { min, max } = range
  if (min === null || max === null) return null

  const override = resolveGenderOverride(field, gender)
  const usingGenderRange =
    !!override && (toNumber(override.min) !== null || toNumber(override.max) !== null)

  if (usingGenderRange) {
    const parsed = toNumber(override?.step)
    const step =
      parsed !== null && parsed > 0 ? parsed : DEFAULT_GENDER_OVERRIDE_STEP
    const grid = buildStepGrid(min, max, step)
    if (grid.length === 0) return null
    return grid[Math.floor(Math.random() * grid.length)] ?? null
  }

  const value = min + Math.random() * (max - min)
  return Number.isFinite(value) ? Number(value.toFixed(2)) : null
}

export function resolveSeedValue(
  field: FieldDefinition,
  gender: Gender | null | undefined,
): unknown {
  if (!shouldSeedField(field, gender)) return undefined
  const def = resolveDefaultValue(field, gender)
  if (def !== null && def !== undefined && def !== '') return def
  return randomInNormalRange(field, gender)
}
