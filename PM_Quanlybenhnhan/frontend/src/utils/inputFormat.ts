/**
 * Client-side mirrors of ``examinations.input_formats``.
 *
 * Formatters rewrite a raw entered value on blur. They are keyed by
 * ``input_format`` code, never by field key.
 */

export type InputFormat = 'bp_slash'

export function formatBpSlash(value: unknown): unknown {
  if (value === null || value === undefined || typeof value === 'boolean') {
    return value
  }

  let text: string
  let sourceWasNumeric = false
  if (typeof value === 'number') {
    if (!Number.isInteger(value)) return value
    text = String(value)
    sourceWasNumeric = true
  } else {
    text = String(value).trim()
  }

  if (!text) return value

  const compact = text.replace(/ /g, '')
  if (compact.includes('/')) {
    const parts = compact.split('/')
    if (parts.length === 2 && parts[0] && parts[1] && /^\d+$/.test(parts[0]) && /^\d+$/.test(parts[1])) {
      return `${parts[0]}/${parts[1]}`
    }
    return sourceWasNumeric ? value : text
  }

  if (/^\d{4,5}$/.test(compact)) {
    return `${compact.slice(0, -2)}/${compact.slice(-2)}`
  }

  return sourceWasNumeric ? value : text
}

const FORMATTERS: Record<string, (value: unknown) => unknown> = {
  bp_slash: formatBpSlash,
}

export function applyInputFormat(format: string | undefined, value: unknown): unknown {
  if (!format) return value
  const formatter = FORMATTERS[format]
  return formatter ? formatter(value) : value
}
