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
      html: '<div><h1>Candidate</h1></div>',
      format: 'pdf',
    })

    expect(fetch).toHaveBeenCalledWith('/api/v1/export/render', expect.objectContaining({ method: 'POST' }))
    expect(result.filename).toBe('resume-test.pdf')
    await expect(result.blob.text()).resolves.toBe('pdf-bytes')
  })

  it('uses a fallback filename when the response omits content-disposition', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(new Blob(['png']), { status: 200 }))

    const result = await exportResume({
      html: '<div><h1>Candidate</h1></div>',
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
        html: '   ',
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
        html: '<div><h1>Candidate</h1></div>',
        format: 'pdf',
      }),
    ).rejects.toThrow('PDF 导出服务暂不可用，请稍后重试')
  })

  it('attaches the current access token when one exists', async () => {
    setTokens({ access_token: 'access-123', refresh_token: 'refresh-123' })
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(new Blob(['pdf']), { status: 200 }))

    await exportResume({
      html: '<div><h1>Candidate</h1></div>',
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

  it('posts html + format only (no markdown/style_id — spec 027 US1)', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(new Blob(['pdf']), { status: 200 }),
    )

    await exportResume({
      html: '<div class="resume-style-classic"><h1>Hi</h1></div>',
      format: 'pdf',
    })

    const call = fetchSpy.mock.calls[0]
    const body = JSON.parse((call[1] as RequestInit).body as string)
    expect(body.html).toBe('<div class="resume-style-classic"><h1>Hi</h1></div>')
    expect(body.format).toBe('pdf')
    // Old fields must NOT be sent — backend rejects unknown fields gracefully
    // but we want the contract to be explicit.
    expect(body.markdown).toBeUndefined()
    expect(body.style_id).toBeUndefined()
  })
})
