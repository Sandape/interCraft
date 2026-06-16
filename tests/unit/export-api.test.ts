import { beforeEach, describe, expect, it, vi } from 'vitest'
import { exportResume } from '@/api/export'
import { clearTokens, setTokens } from '@/api/token-storage'

describe('exportResume', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    clearTokens()
  })

  it('returns a blob and filename from content-disposition', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('pdf-bytes', {
        status: 200,
        headers: {
          'content-type': 'application/pdf',
          'content-disposition': 'attachment; filename="resume-test.pdf"',
        },
      }),
    )

    const result = await exportResume({
      markdown: '# Candidate',
      style_id: 'compact-one-page',
      format: 'pdf',
    })

    expect(fetch).toHaveBeenCalledWith('/api/v1/export/render', expect.objectContaining({ method: 'POST' }))
    expect(result.filename).toBe('resume-test.pdf')
    await expect(result.blob.text()).resolves.toBe('pdf-bytes')
  })

  it('uses a fallback filename when the response omits content-disposition', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(new Blob(['png']), { status: 200 }))

    const result = await exportResume({
      markdown: '# Candidate',
      style_id: 'compact-one-page',
      format: 'png',
    })

    expect(result.filename).toBe('resume.png')
  })

  it('throws the structured server message for validation errors', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          error: 'EMPTY_CONTENT',
          message: 'Resume content is empty.',
          request_id: 'req-1',
        }),
        { status: 400, headers: { 'content-type': 'application/json' } },
      ),
    )

    await expect(
      exportResume({
        markdown: '',
        style_id: 'compact-one-page',
        format: 'pdf',
      }),
    ).rejects.toThrow(/^Resume content is empty\.$/)
  })

  it('keeps the renderer unavailable fallback message for 503 responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          error: 'SERVICE_UNAVAILABLE',
          message: 'Renderer is unavailable.',
          request_id: 'req-1',
        }),
        { status: 503, headers: { 'content-type': 'application/json' } },
      ),
    )

    await expect(
      exportResume({
        markdown: '# Candidate',
        style_id: 'compact-one-page',
        format: 'pdf',
      }),
    ).rejects.toThrow('PDF 导出服务暂不可用，请稍后重试')
  })

  it('attaches the current access token when one exists', async () => {
    setTokens({ access_token: 'access-123', refresh_token: 'refresh-123' })
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(new Blob(['pdf']), { status: 200 }))

    await exportResume({
      markdown: '# Candidate',
      style_id: 'compact-one-page',
      format: 'pdf',
    })

    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/export/render',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer access-123',
          'X-Request-ID': 'test-request-id',
        }),
      }),
    )
  })
})
