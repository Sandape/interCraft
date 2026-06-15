const EXPORT_BASE = '/api/v1/export'

export type ExportFormat = 'pdf' | 'png' | 'jpeg'

export interface ExportRequest {
  markdown: string
  style_id: string
  format: ExportFormat
  locale?: string
}

export async function exportResume(request: ExportRequest): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${EXPORT_BASE}/render`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!res.ok) {
    if (res.status === 503 || res.status === 502) {
      throw new Error('PDF 导出服务暂不可用，请稍后重试')
    }
    const text = await res.text().catch(() => '')
    throw new Error(text || `导出失败 (${res.status})`)
  }

  const contentDisposition = res.headers.get('content-disposition')
  const filename = contentDisposition?.match(/filename="?([^"]+)"?/)?.[1] ?? `resume.${request.format}`

  const blob = await res.blob()
  return { blob, filename }
}
