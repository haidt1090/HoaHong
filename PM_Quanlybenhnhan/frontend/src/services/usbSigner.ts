import {
  documentDigestBase64,
  parseCertificate,
  sha256Base64Of,
  signatureDocument,
  signedInfoBytes,
} from './xmldsig'

const TOKEN_PORTS = [8888, 18888, 18889]

interface TokenSession {
  token: string
  serialNumber: string
  certificateB64: string
}

let session: TokenSession | null = null
let tokenBaseUrl: string | null = null

export interface UsbSignerStatus {
  ok: boolean
  subject: string
}

export async function usbSignerStatus(): Promise<UsbSignerStatus> {
  await tokenPost('/GetToken', {}, 3000)
  return { ok: true, subject: '' }
}

export function resetUsbSignerSession(): void {
  session = null
  tokenBaseUrl = null
}

export async function signXmlWithUsbToken(xml: string): Promise<string> {
  const current = await ensureSession()
  const digest = await documentDigestBase64(xml)
  const signedInfo = signedInfoBytes(xml, digest)
  const hash = await sha256Base64Of(signedInfo)
  const signature = await tokenPost(
    '/SignHash',
    {
      token: current.token,
      data: hash,
      serialNumber: current.serialNumber,
      hashAlgo: 'SHA256',
    },
    180000,
  )
  const cert = parseCertificate(current.certificateB64)
  return signatureDocument(xml, digest, signature, cert)
}

async function ensureSession(): Promise<TokenSession> {
  if (session) return session
  const token = await tokenPost('/GetToken', {}, 5000)
  const serialNumber = await tokenPost('/GetSerialNumber', { token }, 180000)
  const certificateB64 = await tokenPost(
    '/GetCert',
    { token, serialNumber },
    30000,
  )
  session = { token, serialNumber, certificateB64 }
  return session
}

async function resolveTokenBaseUrl(): Promise<string> {
  if (tokenBaseUrl) return tokenBaseUrl
  for (const port of TOKEN_PORTS) {
    const candidate = `http://localhost:${port}`
    try {
      const response = await fetch(`${candidate}/GetToken`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
        signal: AbortSignal.timeout(3000),
      })
      if (response.ok) {
        tokenBaseUrl = candidate
        return candidate
      }
    } catch {
      continue
    }
  }
  throw new Error(
    'Chưa thấy TokenService trên máy này. Cắm USB của cơ sở khám và mở TokenService ở khay hệ thống.',
  )
}

async function tokenPost(path: string, body: object, timeoutMs: number): Promise<string> {
  const baseUrl = await resolveTokenBaseUrl()
  let response: Response
  try {
    response = await fetch(`${baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
    })
  } catch {
    session = null
    tokenBaseUrl = null
    throw new Error(
      'Chưa thấy TokenService trên máy này. Cắm USB của cơ sở khám và mở TokenService ở khay hệ thống.',
    )
  }
  const text = (await response.text()).replace(/\s+/g, '')
  if (!response.ok || !text || text === 'E04') {
    session = null
    throw new Error(
      'USB của cơ sở khám chưa sẵn sàng. Rút ra cắm lại, mở TokenService, rồi thử đồng bộ lại.',
    )
  }
  return text
}
