import { deviceFingerprint } from './device-fingerprint'
import { newRequestId } from './env'
import { getAccessToken } from './token-storage'

const EXPORT_BASE = '/api/v1/export'

export type ExportFormat = 'pdf' | 'png' | 'jpeg'

export interface ExportRequest {
  markdown: string
  style_id: string
  format: ExportFormat
  locale?: string
}

export async function exportResume(request: ExportRequest): Promise<{ blob: Blob; filename: string }> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Request-ID': newRequestId(),
    'X-Device-Fingerprint': deviceFingerprint(),
  }
  const access = getAccessToken()
  if (access) headers.Authorization = `Bearer ${access}`

  const res = await fetch(`${EXPORT_BASE}/render`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  })

  if (!res.ok) {
    if (res.status === 503 || res.status === 502) {
      throw new Error('PDF 导出服务暂不可用，请稍后重试')
    }
    const message = await readErrorMessage(res)
    throw new Error(message || `导出失败 (${res.status})`)
  }

  const contentDisposition = res.headers.get('content-disposition')
  const filename = contentDisposition?.match(/filename="?([^"]+)"?/)?.[1] ?? `resume.${request.format}`

  const blob = await res.blob()
  return { blob, filename }
}

async function readErrorMessage(res: Response): Promise<string> {
  const contentType = res.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    const body = await res.json().catch(() => null) as { message?: unknown; error?: unknown } | null
    if (typeof body?.message === 'string' && body.message.trim()) return body.message
    if (typeof body?.error === 'string' && body.error.trim()) return body.error
  }
  return res.text().catch(() => '')
}
