/**
 * Evaluate a formula expression against a data context.
 *
 * Syntax:
 * - Field references: {field_key}
 * - Basic math: + - * / ^ ( )
 * - Conditional: IF(condition, true_value, false_value)
 *   - Comparisons: < > <= >= = !=
 */

import type { FieldDefinition, Gender } from '@/types'
import { shouldSeedField } from '@/utils/field'

interface Token {
  type: 'number' | 'string' | 'field' | 'op' | 'lparen' | 'rparen' | 'comma' | 'keyword'
  value: string
}

const IF_HEAD = /^IF\s*\(/i
const MATH_CHARS = /[{}+\-*/^()]/

function evaluateFormula(formula: string, data: Record<string, unknown>): unknown {
  if (!formula || !formula.trim()) return null

  let text = formula.trim()
  if (text.startsWith('=')) text = text.slice(1).trim()

  const match = text.match(IF_HEAD)
  if (match) {
    return evaluateIf(text.slice(match[0].length), data)
  }

  return evaluateExpression(text, data)
}

function normalizeFormulaResult(result: unknown): unknown {
  if (typeof result === 'number' && Number.isFinite(result)) {
    return Math.round(result * 100) / 100
  }
  return result
}

/** Evaluate every field that has a formula (multi-pass for dependencies). */
function evaluateComputedFields(
  fields: FieldDefinition[],
  data: Record<string, unknown>,
  gender?: Gender | null,
): Record<string, unknown> {
  const updated: Record<string, unknown> = { ...data }
  const formulaFields = [...fields]
    .filter((f) => f.formula?.trim() && f.key && shouldSeedField(f, gender))
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))

  if (!formulaFields.length) return updated

  for (let pass = 0; pass < formulaFields.length; pass++) {
    let changed = false
    for (const field of formulaFields) {
      const result = normalizeFormulaResult(evaluateFormula(field.formula as string, updated))
      if (updated[field.key] !== result) {
        updated[field.key] = result
        changed = true
      }
    }
    if (!changed) break
  }
  return updated
}

function evaluateExpression(expr: string, data: Record<string, unknown>): number {
  const tokens = tokenize(expr, data)
  return parseAddSub(tokens)
}

function evaluateIf(inner: string, data: Record<string, unknown>): unknown {
  const args = splitArgs(inner)
  if (args.length < 3) return null

  const condition = args[0].trim()
  const trueVal = args[1].trim()
  const falseVal = args.length >= 3 ? args[2].trim() : '""'

  const condResult = evaluateComparison(condition, data)
  return coerceIfBranch(condResult ? trueVal : falseVal, data)
}

function coerceIfBranch(resultExpr: string, data: Record<string, unknown>): unknown {
  const stripped = resultExpr.trim()
  if (IF_HEAD.test(stripped)) {
    return evaluateFormula(stripped, data)
  }

  if (
    stripped.length >= 2 &&
    stripped[0] === stripped[stripped.length - 1] &&
    (stripped[0] === '"' || stripped[0] === "'")
  ) {
    return stripped.slice(1, -1)
  }

  if (!isNaN(Number(stripped)) && stripped !== '') {
    return Number(stripped)
  }

  if (!stripped.includes('{') && !MATH_CHARS.test(stripped)) {
    return stripped
  }

  return evaluateFormula(stripped, data)
}

function evaluateComparison(cond: string, data: Record<string, unknown>): boolean {
  const operators = ['>=', '<=', '!=', '=', '<', '>']
  for (const op of operators) {
    const idx = cond.indexOf(op)
    if (idx !== -1) {
      const left = cond.slice(0, idx).trim()
      const right = cond.slice(idx + op.length).trim()
      const lVal = resolveValue(left, data)
      const rVal = resolveValue(right, data)

      if (typeof lVal === 'string' && typeof rVal === 'string') {
        if (op === '=') return lVal === rVal
        if (op === '!=') return lVal !== rVal
        return false
      }

      const lNum = Number(lVal)
      const rNum = Number(rVal)

      switch (op) {
        case '<':
          return lNum < rNum
        case '>':
          return lNum > rNum
        case '<=':
          return lNum <= rNum
        case '>=':
          return lNum >= rNum
        case '=':
          return lNum === rNum
        case '!=':
          return lNum !== rNum
      }
    }
  }
  return !!resolveValue(cond, data)
}

function resolveValue(expr: string, data: Record<string, unknown>): unknown {
  const trimmed = expr.trim()
  if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
    const key = trimmed.slice(1, -1)
    return data[key] ?? 0
  }
  if (!isNaN(Number(trimmed)) && trimmed !== '') return Number(trimmed)
  if (trimmed.startsWith('"') && trimmed.endsWith('"')) return trimmed.slice(1, -1)
  if (trimmed.startsWith("'") && trimmed.endsWith("'")) return trimmed.slice(1, -1)
  return trimmed
}

function tokenize(expr: string, data: Record<string, unknown>): Token[] {
  const tokens: Token[] = []
  let i = 0

  while (i < expr.length) {
    const ch = expr[i]

    if (/\s/.test(ch)) {
      i++
      continue
    }

    if (ch === '(') {
      tokens.push({ type: 'lparen', value: '(' })
      i++
      continue
    }
    if (ch === ')') {
      tokens.push({ type: 'rparen', value: ')' })
      i++
      continue
    }
    if (ch === ',') {
      tokens.push({ type: 'comma', value: ',' })
      i++
      continue
    }

    if ('+-*/^'.includes(ch)) {
      tokens.push({ type: 'op', value: ch })
      i++
      continue
    }

    if (/[0-9.]/.test(ch)) {
      let num = ''
      while (i < expr.length && /[0-9.]/.test(expr[i])) {
        num += expr[i]
        i++
      }
      tokens.push({ type: 'number', value: num })
      continue
    }

    if (ch === '{') {
      let key = ''
      i++ // skip {
      while (i < expr.length && expr[i] !== '}') {
        key += expr[i]
        i++
      }
      i++ // skip }
      const raw = data[key.trim()]
      const val = raw !== undefined && raw !== null && raw !== '' ? Number(raw) : 0
      tokens.push({ type: 'number', value: String(isNaN(val) ? 0 : val) })
      continue
    }

    if (/[a-zA-Z]/.test(ch)) {
      let word = ''
      while (i < expr.length && /[a-zA-Z_]/.test(expr[i])) {
        word += expr[i]
        i++
      }
      tokens.push({ type: 'keyword', value: word })
      continue
    }

    i++
  }

  return tokens
}

// Recursive descent parser

let pos = 0
let tok: Token[] = []

function parseAddSub(tokens: Token[]): number {
  tok = tokens
  pos = 0
  return expr()
}

function expr(): number {
  let result = term()
  while (pos < tok.length) {
    if (tok[pos].type === 'op' && tok[pos].value === '+') {
      pos++
      result += term()
      continue
    }
    if (tok[pos].type === 'op' && tok[pos].value === '-') {
      pos++
      result -= term()
      continue
    }
    break
  }
  return result
}

function term(): number {
  let result = power()
  while (pos < tok.length) {
    if (tok[pos].type === 'op' && tok[pos].value === '*') {
      pos++
      result *= power()
      continue
    }
    if (tok[pos].type === 'op' && tok[pos].value === '/') {
      pos++
      const divisor = power()
      result = divisor === 0 ? 0 : result / divisor
      continue
    }
    break
  }
  return result
}

function power(): number {
  let result = factor()
  while (pos < tok.length) {
    if (tok[pos].type === 'op' && tok[pos].value === '^') {
      pos++
      result = Math.pow(result, factor())
      continue
    }
    break
  }
  return result
}

function factor(): number {
  if (pos >= tok.length) return 0
  const t = tok[pos]

  if (t.type === 'number') {
    pos++
    return Number(t.value)
  }

  if (t.type === 'lparen') {
    pos++ // skip (
    const result = expr()
    if (pos < tok.length && tok[pos].type === 'rparen') {
      pos++ // skip )
    }
    return result
  }

  // Unary minus
  if (t.type === 'op' && t.value === '-') {
    pos++
    return -factor()
  }

  return 0
}

function splitArgs(text: string): string[] {
  const args: string[] = []
  let depth = 0
  let current = ''
  let i = 0
  let inQuote = false
  let quoteChar = ''

  while (i < text.length) {
    const ch = text[i]
    if (inQuote) {
      current += ch
      if (ch === quoteChar) inQuote = false
    } else if (ch === '"' || ch === "'") {
      inQuote = true
      quoteChar = ch
      current += ch
    } else if (ch === '(') {
      depth++
      current += ch
    } else if (ch === ')') {
      depth--
      if (depth < 0) break
      current += ch
    } else if (ch === ',' && depth === 0) {
      args.push(current)
      current = ''
    } else {
      current += ch
    }
    i++
  }
  if (current.trim()) args.push(current)
  return args
}

export { evaluateFormula, evaluateComputedFields }
