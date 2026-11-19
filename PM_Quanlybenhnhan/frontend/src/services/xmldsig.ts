// XMLDSig (RSA-SHA256) matching .NET SignedXml for KHAMSUCKHOE documents.
// The USB token only signs a SHA-256 digest. This module builds the
// Signature element and returns the digest the token must sign.

const DSIG = 'http://www.w3.org/2000/09/xmldsig#'
const C14N = 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
const RSA_SHA256 = 'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256'
const SHA256 = 'http://www.w3.org/2001/04/xmlenc#sha256'
const ENVELOPED = 'http://www.w3.org/2000/09/xmldsig#enveloped-signature'

const OID_NAMES: Record<string, string> = {
  '2.5.4.3': 'CN',
  '2.5.4.6': 'C',
  '2.5.4.7': 'L',
  '2.5.4.8': 'S',
  '2.5.4.10': 'O',
  '2.5.4.11': 'OU',
  '2.5.4.12': 'T',
  '2.5.4.5': 'SERIALNUMBER',
  '1.2.840.113549.1.9.1': 'E',
}

export interface ParsedCertificate {
  subject: string
  modulusB64: string
  exponentB64: string
  certificateB64: string
}

interface XmlAttr {
  name: string
  value: string
}

interface XmlEl {
  name: string
  attrs: XmlAttr[]
  children: Array<XmlEl | string>
}

export function documentDigestBase64(xml: string): Promise<string> {
  return sha256Base64(new TextEncoder().encode(canonicalizeDocument(xml)))
}

export function signedInfoBytes(xml: string, digestB64: string): Uint8Array {
  return new TextEncoder().encode(canonicalSignedInfo(xml, digestB64))
}

export function signatureDocument(
  xml: string,
  digestB64: string,
  signatureB64: string,
  cert: ParsedCertificate,
): string {
  const id = crypto.randomUUID()
  const signature =
    `<Signature Id="${id}" xmlns="${DSIG}">` +
    signedInfoMarkup(digestB64) +
    `<SignatureValue>${signatureB64}</SignatureValue>` +
    `<KeyInfo><KeyValue><RSAKeyValue><Modulus>${cert.modulusB64}</Modulus>` +
    `<Exponent>${cert.exponentB64}</Exponent></RSAKeyValue></KeyValue>` +
    `<X509Data><X509SubjectName>${escapeText(cert.subject)}</X509SubjectName>` +
    `<X509Certificate>${cert.certificateB64}</X509Certificate></X509Data></KeyInfo>` +
    `</Signature>`
  return bytesToBase64(new TextEncoder().encode(signature))
}

export function parseCertificate(certificateB64: string): ParsedCertificate {
  const cleaned = certificateB64
    .replace(/-----BEGIN ?CERTIFICATE-----/g, '')
    .replace(/-----END ?CERTIFICATE-----/g, '')
    .replace(/\s+/g, '')
  const bytes = base64ToBytes(cleaned)
  const cert = readElement(bytes, 0)
  if (cert.tag !== 0x30) throw new Error('Chứng thư USB không đúng định dạng.')
  const tbs = readElement(bytes, cert.valueStart)
  if (tbs.tag !== 0x30) throw new Error('Chứng thư USB không đúng định dạng.')
  let cursor = tbs.valueStart
  const version = peek(bytes, cursor)
  if (version.tag === 0xa0) cursor = version.next
  cursor = readElement(bytes, cursor).next
  cursor = readElement(bytes, cursor).next
  cursor = readElement(bytes, cursor).next
  cursor = readElement(bytes, cursor).next
  const subject = readElement(bytes, cursor)
  cursor = subject.next
  const spki = readElement(bytes, cursor)
  const subjectName = formatSubject(bytes, subject)
  const { modulus, exponent } = readRsaPublicKey(bytes, spki)
  return {
    subject: subjectName,
    modulusB64: bytesToBase64(modulus),
    exponentB64: bytesToBase64(exponent),
    certificateB64: cleaned,
  }
}

function canonicalizeDocument(xml: string): string {
  const root = parseRoot(xml)
  return emit(root)
}

function canonicalSignedInfo(xml: string, digestB64: string): string {
  const namespaces = rootNamespaces(parseRoot(xml))
  const decls = Object.keys(namespaces)
    .sort()
    .map((prefix) => ` xmlns:${prefix}="${escapeAttr(namespaces[prefix])}"`)
    .join('')
  return (
    `<SignedInfo xmlns="${DSIG}"${decls}>` +
    `<CanonicalizationMethod Algorithm="${C14N}"></CanonicalizationMethod>` +
    `<SignatureMethod Algorithm="${RSA_SHA256}"></SignatureMethod>` +
    `<Reference URI=""><Transforms>` +
    `<Transform Algorithm="${ENVELOPED}"></Transform>` +
    `</Transforms>` +
    `<DigestMethod Algorithm="${SHA256}"></DigestMethod>` +
    `<DigestValue>${digestB64}</DigestValue>` +
    `</Reference></SignedInfo>`
  )
}

function signedInfoMarkup(digestB64: string): string {
  return (
    `<SignedInfo>` +
    `<CanonicalizationMethod Algorithm="${C14N}" />` +
    `<SignatureMethod Algorithm="${RSA_SHA256}" />` +
    `<Reference URI=""><Transforms>` +
    `<Transform Algorithm="${ENVELOPED}" />` +
    `</Transforms>` +
    `<DigestMethod Algorithm="${SHA256}" />` +
    `<DigestValue>${digestB64}</DigestValue>` +
    `</Reference></SignedInfo>`
  )
}

function rootNamespaces(root: XmlEl): Record<string, string> {
  const found: Record<string, string> = {}
  for (const attr of root.attrs) {
    if (attr.name.startsWith('xmlns:')) found[attr.name.slice(6)] = attr.value
  }
  return found
}

function emit(el: XmlEl): string {
  const ns = el.attrs
    .filter((attr) => attr.name === 'xmlns' || attr.name.startsWith('xmlns:'))
    .sort((a, b) => a.name.localeCompare(b.name))
  const plain = el.attrs
    .filter((attr) => attr.name !== 'xmlns' && !attr.name.startsWith('xmlns:'))
    .sort((a, b) => a.name.localeCompare(b.name))
  const attrs = [...ns, ...plain]
    .map((attr) => ` ${attr.name}="${escapeAttr(attr.value)}"`)
    .join('')
  const inner = el.children
    .map((child) => (typeof child === 'string' ? escapeText(child) : emit(child)))
    .join('')
  return `<${el.name}${attrs}>${inner}</${el.name}>`
}

function parseRoot(xml: string): XmlEl {
  let index = 0
  if (xml.charCodeAt(0) === 0xfeff) index = 1
  if (xml.startsWith('<?', index)) {
    const end = xml.indexOf('?>', index)
    index = end + 2
  }
  skipSpace(xml, () => index, (next) => {
    index = next
  })
  const parsed = parseElement(xml, index)
  return parsed.el
}

function parseElement(xml: string, start: number): { el: XmlEl; next: number } {
  if (xml[start] !== '<') throw new Error('XML cần ký không hợp lệ.')
  let index = start + 1
  const nameEnd = xml.slice(index).search(/[\s>/]/)
  const name = xml.slice(index, index + nameEnd)
  index += nameEnd
  const attrs: XmlAttr[] = []
  while (index < xml.length && xml[index] !== '>' && xml[index] !== '/') {
    while (xml[index] === ' ' || xml[index] === '\n' || xml[index] === '\r' || xml[index] === '\t') {
      index += 1
    }
    if (xml[index] === '>' || xml[index] === '/') break
    const eq = xml.indexOf('=', index)
    const attrName = xml.slice(index, eq).trim()
    const quote = xml[eq + 1]
    const valueEnd = xml.indexOf(quote, eq + 2)
    attrs.push({ name: attrName, value: unescapeXml(xml.slice(eq + 2, valueEnd)) })
    index = valueEnd + 1
  }
  if (xml[index] === '/') {
    return { el: { name, attrs, children: [] }, next: xml.indexOf('>', index) + 1 }
  }
  index += 1
  const children: Array<XmlEl | string> = []
  let text = ''
  while (index < xml.length) {
    if (xml.startsWith('</', index)) {
      if (text) children.push(unescapeXml(text))
      const close = xml.indexOf('>', index)
      return { el: { name, attrs, children }, next: close + 1 }
    }
    if (xml[index] === '<') {
      if (text) {
        children.push(unescapeXml(text))
        text = ''
      }
      const child = parseElement(xml, index)
      children.push(child.el)
      index = child.next
      continue
    }
    text += xml[index]
    index += 1
  }
  throw new Error('XML cần ký không hợp lệ.')
}

function skipSpace(xml: string, get: () => number, set: (next: number) => void): void {
  let index = get()
  while (xml[index] === ' ' || xml[index] === '\n' || xml[index] === '\r' || xml[index] === '\t') {
    index += 1
  }
  set(index)
}

function escapeText(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\r/g, '&#xD;')
}

function escapeAttr(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/"/g, '&quot;')
    .replace(/\t/g, '&#x9;')
    .replace(/\n/g, '&#xA;')
    .replace(/\r/g, '&#xD;')
}

function unescapeXml(value: string): string {
  return value
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, '&')
}

interface Asn1 {
  tag: number
  valueStart: number
  valueEnd: number
  next: number
}

function peek(bytes: Uint8Array, offset: number): Asn1 {
  return readElement(bytes, offset)
}

function readElement(bytes: Uint8Array, offset: number): Asn1 {
  const tag = bytes[offset]
  let index = offset + 1
  let length = bytes[index]
  index += 1
  if (length & 0x80) {
    const count = length & 0x7f
    length = 0
    for (let i = 0; i < count; i += 1) {
      length = (length << 8) | bytes[index]
      index += 1
    }
  }
  const valueStart = index
  const valueEnd = index + length
  return { tag, valueStart, valueEnd, next: valueEnd }
}

function formatSubject(bytes: Uint8Array, subject: Asn1): string {
  const parts: string[] = []
  let cursor = subject.valueStart
  while (cursor < subject.valueEnd) {
    const set = readElement(bytes, cursor)
    cursor = set.next
    let rdn = set.valueStart
    const group: string[] = []
    while (rdn < set.valueEnd) {
      const seq = readElement(bytes, rdn)
      rdn = seq.next
      const oid = readElement(bytes, seq.valueStart)
      const value = readElement(bytes, oid.next)
      const name = OID_NAMES[decodeOid(bytes.subarray(oid.valueStart, oid.valueEnd))] ??
        `OID.${decodeOid(bytes.subarray(oid.valueStart, oid.valueEnd))}`
      group.push(`${name}=${escapeDn(decodeString(bytes, value))}`)
    }
    parts.push(group.join('+'))
  }
  return parts.reverse().join(', ')
}

function escapeDn(value: string): string {
  if (/[,+="<>;]/.test(value)) return `"${value.replace(/"/g, '""')}"`
  return value
}

function readRsaPublicKey(bytes: Uint8Array, spki: Asn1): { modulus: Uint8Array; exponent: Uint8Array } {
  const alg = readElement(bytes, spki.valueStart)
  const bitString = readElement(bytes, alg.next)
  const keyStart = bitString.valueStart + 1
  const key = readElement(bytes, keyStart)
  const modulus = readElement(bytes, key.valueStart)
  const exponent = readElement(bytes, modulus.next)
  return {
    modulus: unsignedInteger(bytes.subarray(modulus.valueStart, modulus.valueEnd)),
    exponent: unsignedInteger(bytes.subarray(exponent.valueStart, exponent.valueEnd)),
  }
}

function unsignedInteger(bytes: Uint8Array): Uint8Array {
  if (bytes.length > 1 && bytes[0] === 0x00) return bytes.subarray(1)
  return bytes
}

function decodeOid(bytes: Uint8Array): string {
  const parts = [Math.floor(bytes[0] / 40), bytes[0] % 40]
  let value = 0
  for (let i = 1; i < bytes.length; i += 1) {
    value = (value << 7) | (bytes[i] & 0x7f)
    if ((bytes[i] & 0x80) === 0) {
      parts.push(value)
      value = 0
    }
  }
  return parts.join('.')
}

function decodeString(bytes: Uint8Array, node: Asn1): string {
  const slice = bytes.subarray(node.valueStart, node.valueEnd)
  if (node.tag === 0x1e) {
    const chars: number[] = []
    for (let i = 0; i + 1 < slice.length; i += 2) chars.push((slice[i] << 8) | slice[i + 1])
    return String.fromCharCode(...chars)
  }
  return new TextDecoder().decode(slice)
}

async function sha256Base64(bytes: Uint8Array): Promise<string> {
  const buffer = new ArrayBuffer(bytes.byteLength)
  new Uint8Array(buffer).set(bytes)
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return bytesToBase64(new Uint8Array(digest))
}

export async function sha256Base64Of(bytes: Uint8Array): Promise<string> {
  return sha256Base64(bytes)
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = ''
  const size = 0x8000
  for (let i = 0; i < bytes.length; i += size) {
    binary += String.fromCharCode(...bytes.subarray(i, i + size))
  }
  return btoa(binary)
}

function base64ToBytes(value: string): Uint8Array {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  return bytes
}
