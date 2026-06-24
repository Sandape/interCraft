import { deviceFingerprint } from './device-fingerprint'
import { newRequestId } from './env'
import { getAccessToken } from './token-storage'
import { ExportError } from '@/lib/apiErrorToMessage'

const EXPORT_BASE = '/api/v1/export'

export type ExportFormat = 'pdf' | 'png' | 'jpeg'

export interface ExportRequest {
  /**
   * Pre-rendered HTML (output of `renderMarkdown` from `@/lib/resume-renderer`).
   * The backend wraps this in a full HTML document and feeds it to Playwright.
   * Must be non-empty and ≤1MB after UTF-8 encoding.
   */
  html: string
  format: ExportFormat
  /** Optional locale hint (default 'zh'). */
  locale?: string
}

export async function exportResume(request: ExportRequest): Promise<{ blob: Blob; filename: string }> {
  const requestId = newRequestId()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Request-ID': requestId,
    'X-Device-Fingerprint': deviceFingerprint(),
  }
  const access = getAccessToken()
  if (access) headers.Authorization = `Bearer ${access}`

  let res: Response
  try {
    res = await fetch(`${EXPORT_BASE}/render`, {
      method: 'POST',
      headers,
      body: JSON.stringify(request),
    })
  } catch (e) {
    throw new ExportError(
      '导出服务暂不可用，请稍后重试',
      0,
      'NETWORK_ERROR',
      requestId,
    )
  }

  if (!res.ok) {
    if (res.status === 503 || res.status === 502) {
      throw new ExportError(
        'PDF 导出服务暂不可用，请稍后重试',
        res.status,
        'SERVICE_UNAVAILABLE',
        requestId,
      )
    }
    const { message, code } = await readErrorPayload(res)
    throw new ExportError(message || `导出失败 (${res.status})`, res.status, code, requestId)
  }

  const contentDisposition = res.headers.get('content-disposition')
  const filename = contentDisposition?.match(/filename="?([^"]+)"?/)?.[1] ?? `resume.${request.format}`

  const blob = await res.blob()
  return { blob, filename }
}

async function readErrorPayload(res: Response): Promise<{ message?: string; code?: string }> {
  const contentType = res.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    const body = await res.json().catch(() => null) as
      | { message?: unknown; error?: unknown; code?: unknown }
      | null
    if (body) {
      const message = typeof body.message === 'string' ? body.message : undefined
      const error = typeof body.error === 'string' ? body.error : undefined
      const code = typeof body.code === 'string' ? body.code : undefined
      return { message: message ?? error, code }
    }
  }
  const text = await res.text().catch(() => '')
  return { message: text || undefined }
}
