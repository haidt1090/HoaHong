import JSZip from 'jszip'
import { renderAsync } from 'docx-preview'

const word = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
const token = /\$(?:\{([^{}\r\n]+)\}|([\p{L}_][\p{L}\p{N}_]*))/gu
export function keyword(value: string): string {
  return value
    .toLowerCase()
    .replaceAll('đ', 'd')
    .normalize('NFD')
    .replace(/[^a-z0-9]/g, '')
}

export async function prepareWord(file: File) {
  const zip = await JSZip.loadAsync(await file.arrayBuffer())
  if (!zip.file('word/document.xml')) throw new Error('Tệp mẫu phải là Word .docx.')
  await removeExternalLinks(zip)
  const parts = await Promise.all(
    Object.values(zip.files)
      .filter((part) =>
        /^word\/(document|header\d+|footer\d+|footnotes|endnotes)\.xml$/.test(part.name),
      )
      .map(async (part) => [part.name, await part.async('string')] as const),
  )
  const parser = new DOMParser()
  const names = new Set<string>()
  for (const [, xml] of parts) {
    const doc = parser.parseFromString(xml, 'application/xml')
    for (const nodes of paragraphs(doc)) {
      for (const match of nodes
        .map((node) => node.textContent)
        .join('')
        .matchAll(token)) {
        names.add(match[1] ?? match[2]!)
      }
    }
  }
  return {
    names: [...names],
    async fill(values: Record<string, string>) {
      for (const [path, xml] of parts) {
        const doc = parser.parseFromString(xml, 'application/xml')
        for (const nodes of paragraphs(doc)) {
          const text = nodes.map((node) => node.textContent ?? '').join('')
          const positions = nodes.map((node) => node.textContent?.length ?? 0)
          for (const match of Array.from(text.matchAll(token)).reverse()) {
            const start = match.index!
            const end = start + match[0].length
            let offset = 0
            for (const [i, node] of nodes.entries()) {
              const length = positions[i]!
              if (start < offset + length && end > offset) {
                const value = node.textContent ?? ''
                const replacement =
                  start >= offset ? (values[keyword(match[1] ?? match[2]!)] ?? '') : ''
                node.textContent =
                  value.slice(0, Math.max(0, start - offset)) +
                  replacement +
                  value.slice(end - offset)
                node.setAttributeNS('http://www.w3.org/XML/1998/namespace', 'xml:space', 'preserve')
              }
              offset += length
            }
          }
        }
        zip.file(path, new XMLSerializer().serializeToString(doc))
      }
      return zip.generateAsync({ type: 'arraybuffer' })
    },
  }
}

async function removeExternalLinks(zip: JSZip) {
  const relationships = Object.values(zip.files).filter((part) => part.name.endsWith('.rels'))
  for (const part of relationships) {
    const doc = new DOMParser().parseFromString(await part.async('string'), 'application/xml')
    const external = Array.from(doc.getElementsByTagNameNS('*', 'Relationship')).filter(
      (link) => link.getAttribute('TargetMode')?.toLowerCase() === 'external',
    )
    if (external.length) {
      external.forEach((link) => link.remove())
      zip.file(part.name, new XMLSerializer().serializeToString(doc))
    }
  }
}

function paragraphs(doc: Document): Element[][] {
  return Array.from(doc.getElementsByTagNameNS(word, 'p'), (paragraph) =>
    Array.from(paragraph.getElementsByTagNameNS(word, 't')).filter(
      (node) =>
        Array.from(ancestors(node)).find(
          (parent) => parent.namespaceURI === word && parent.localName === 'p',
        ) === paragraph,
    ),
  )
}

function* ancestors(node: Element) {
  for (let parent = node.parentElement; parent; parent = parent.parentElement) yield parent
}

export async function printWordBatch(
  template: Awaited<ReturnType<typeof prepareWord>>,
  records: Record<string, string>[],
) {
  const frame = document.createElement('iframe')
  frame.title = 'Bản in báo cáo'
  frame.style.cssText = 'position:fixed;width:0;height:0;border:0'
  document.body.append(frame)
  try {
    const doc = frame.contentDocument!
    const style = doc.createElement('style')
    style.textContent =
      '@media print { .print-person + .print-person { break-before: page; } body { margin: 0; } }'
    doc.head.append(style)
    for (const [index, values] of records.entries()) {
      const section = doc.createElement('div')
      section.className = 'print-person'
      doc.body.append(section)
      await renderAsync(await template.fill(values), section, section, {
        className: `document-${index}`,
        inWrapper: false,
        useBase64URL: true,
        renderAltChunks: false,
      })
    }
    const page = doc.querySelector<HTMLElement>('.print-person section')
    if (page?.style.width && page.style.minHeight) {
      style.textContent += `@page { size: ${page.style.width} ${page.style.minHeight}; margin: 0; }`
    }
    await doc.fonts.ready
    await Promise.all(Array.from(doc.images, (image) => image.decode().catch(() => undefined)))
    const win = frame.contentWindow!
    win.addEventListener('afterprint', () => frame.remove(), { once: true })
    win.focus()
    win.print()
  } catch (error) {
    frame.remove()
    throw error
  }
}
