import { onMounted, onUnmounted } from 'vue'

export interface ShortcutOptions {
  /**
   * When true the shortcut fires even while focus is inside an
   * `<input>`/`<textarea>`/`<select>`/contenteditable element.
   * Defaults to true when the combo contains a non-typeable modifier
   * (`Ctrl`, `Alt`, `Meta`), otherwise false.
   */
  allowInInput?: boolean
  /** Call `event.preventDefault()` before invoking the handler. */
  preventDefault?: boolean
  /** Gate: the shortcut only fires when this returns true. */
  when?: () => boolean
}

interface ParsedCombo {
  ctrl: boolean
  shift: boolean
  alt: boolean
  meta: boolean
  key: string
}

interface Entry {
  parsed: ParsedCombo
  handler: (event: KeyboardEvent) => void
  allowInInput: boolean
  preventDefault: boolean
  when?: () => boolean
}

type Handler = (event: KeyboardEvent) => void

const EDITABLE_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT'])
// Elements that consume plain keys themselves (Enter activates a button,
// Space toggles a checkbox, …). Modifier combos still fire on these.
const INTERACTIVE_TAGS = new Set(['BUTTON', 'A', 'SUMMARY'])

function isEditable(el: Element | null): boolean {
  if (!el) return false
  if (EDITABLE_TAGS.has(el.tagName)) return true
  return (el as HTMLElement).isContentEditable
}

function isInteractive(el: Element | null): boolean {
  if (!el) return false
  if (INTERACTIVE_TAGS.has(el.tagName)) return true
  return el.getAttribute?.('role') === 'button'
}

function parseCombo(combo: string): ParsedCombo {
  const parts = combo
    .toLowerCase()
    .split('+')
    .map((p) => p.trim())
    .filter(Boolean)
  const parsed: ParsedCombo = { ctrl: false, shift: false, alt: false, meta: false, key: '' }
  for (const part of parts) {
    if (part === 'ctrl' || part === 'control') parsed.ctrl = true
    else if (part === 'shift') parsed.shift = true
    else if (part === 'alt') parsed.alt = true
    else if (part === 'meta' || part === 'cmd' || part === 'win') parsed.meta = true
    else parsed.key = part
  }
  return parsed
}

function matches(event: KeyboardEvent, parsed: ParsedCombo): boolean {
  if (event.ctrlKey !== parsed.ctrl) return false
  if (event.metaKey !== parsed.meta) return false
  if (event.altKey !== parsed.alt) return false
  if (event.shiftKey !== parsed.shift) return false
  return event.key.toLowerCase() === parsed.key
}

/**
 * Registers global `keydown` shortcuts scoped to the calling component.
 *
 * - Modifier combos (`Ctrl+S`, `Ctrl+Q`, …) fire even while typing.
 * - Plain keys (`Enter`, `↑`, `↓`, `Delete`, …) are suppressed inside inputs.
 * - Listeners are attached on `onMounted` and detached on `onUnmounted`,
 *   so there is no leak after the component unmounts.
 */
export function useKeyboardShortcuts() {
  const entries: Entry[] = []

  function onKeydown(event: KeyboardEvent): void {
    const target = event.target as Element | null
    const suppressPlainKey = isEditable(target) || isInteractive(target)

    for (const entry of entries) {
      if (!matches(event, entry.parsed)) continue
      if (entry.when && !entry.when()) continue
      if (suppressPlainKey && !entry.allowInInput) continue

      if (entry.preventDefault) event.preventDefault()
      entry.handler(event)
      return
    }
  }

  /** Removes a single entry from the registry. */
  function unregister(entry: Entry): void {
    const idx = entries.indexOf(entry)
    if (idx >= 0) entries.splice(idx, 1)
  }

  /**
   * Registers a combo. Returns a disposer to unregister just this combo.
   * The whole registry is cleared automatically on unmount.
   */
  function register(combo: string, handler: Handler, options: ShortcutOptions = {}): () => void {
    const parsed = parseCombo(combo)
    const hasTypeableModifier = parsed.ctrl || parsed.meta || parsed.alt
    const entry: Entry = {
      parsed,
      handler,
      allowInInput: options.allowInInput ?? hasTypeableModifier,
      preventDefault: options.preventDefault ?? false,
      when: options.when,
    }
    entries.push(entry)
    return () => unregister(entry)
  }

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onUnmounted(() => {
    window.removeEventListener('keydown', onKeydown)
    entries.length = 0
  })

  return { register }
}
