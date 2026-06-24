/**
 * useBranchAvatar — TanStack mutation hooks (spec 027 US9).
 *
 * Verifies via a local MSW server:
 * - upload POSTs to /avatar with FormData and invalidates BRANCHES_KEY +
 *   BRANCH_KEY(branchId) on success.
 * - delete calls DELETE /avatar and invalidates branch queries.
 * - inherit calls POST /avatar/inherit and invalidates branch queries.
 * - error responses do not trigger invalidation.
 */
import { describe, expect, it, beforeAll, afterAll, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { ReactNode } from 'react'

import {
  useDeleteBranchAvatar,
  useInheritBranchAvatar,
  useUploadBranchAvatar,
} from '../useBranchAvatar'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterAll(() => server.close())

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  return { wrapper, qc, invalidateSpy }
}

describe('useUploadBranchAvatar', () => {
  it('POSTs to /avatar with FormData and invalidates branch queries', async () => {
    let received: { url: string; contentType: string | null } = { url: '', contentType: null }
    server.use(
      http.post('http://localhost:8000/api/v1/resume-branches/:id/avatar', ({ request, params }) => {
        received = {
          url: `/api/v1/resume-branches/${params.id}/avatar`,
          contentType: request.headers.get('content-type'),
        }
        return HttpResponse.json({
          branch_id: params.id,
          url: `/api/v1/resume-branches/${params.id}/avatar`,
          content_type: 'image/jpeg',
          byte_size: 12345,
        })
      }),
    )

    const { wrapper, invalidateSpy } = makeWrapper()
    const file = new File(['fake'], 'avatar.png', { type: 'image/png' })
    const { result } = renderHook(() => useUploadBranchAvatar('b1'), { wrapper })

    const out = await result.current.mutateAsync(file)

    expect(received.url).toBe('/api/v1/resume-branches/b1/avatar')
    expect(received.contentType).toContain('multipart/form-data')
    expect(out.branch_id).toBe('b1')

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['resumes', 'branches'] }),
      )
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['resumes', 'branches', 'b1'] }),
      )
    })
  })

  it('surfaces FILE_TOO_LARGE 413 without invalidating', async () => {
    server.use(
      http.post('http://localhost:8000/api/v1/resume-branches/:id/avatar', () =>
        HttpResponse.json(
          { error: { code: 'FILE_TOO_LARGE', message: 'too big' } },
          { status: 413 },
        ),
      ),
    )
    const { wrapper, invalidateSpy } = makeWrapper()
    const file = new File(['x'], 'x.png', { type: 'image/png' })
    const { result } = renderHook(() => useUploadBranchAvatar('b1'), { wrapper })

    await expect(result.current.mutateAsync(file)).rejects.toThrow()
    expect(invalidateSpy).not.toHaveBeenCalled()
  })
})

describe('useDeleteBranchAvatar', () => {
  it('DELETEs /avatar and invalidates branch queries', async () => {
    let method: string | null = null
    server.use(
      http.delete('http://localhost:8000/api/v1/resume-branches/:id/avatar', ({ request }) => {
        method = request.method
        return HttpResponse.json({ ok: true })
      }),
    )
    const { wrapper, invalidateSpy } = makeWrapper()
    const { result } = renderHook(() => useDeleteBranchAvatar('b1'), { wrapper })

    await result.current.mutateAsync()

    expect(method).toBe('DELETE')
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['resumes', 'branches'] }),
      )
    })
  })
})

describe('useInheritBranchAvatar', () => {
  it('POSTs /avatar/inherit and invalidates branch queries', async () => {
    let method: string | null = null
    server.use(
      http.post('http://localhost:8000/api/v1/resume-branches/:id/avatar/inherit', ({ request }) => {
        method = request.method
        return HttpResponse.json({ ok: true })
      }),
    )
    const { wrapper, invalidateSpy } = makeWrapper()
    const { result } = renderHook(() => useInheritBranchAvatar('b2'), { wrapper })

    await result.current.mutateAsync()

    expect(method).toBe('POST')
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['resumes', 'branches', 'b2'] }),
      )
    })
  })

  it('surfaces CANNOT_INHERIT 422', async () => {
    server.use(
      http.post('http://localhost:8000/api/v1/resume-branches/:id/avatar/inherit', () =>
        HttpResponse.json(
          { error: { code: 'CANNOT_INHERIT', message: 'no parent avatar' } },
          { status: 422 },
        ),
      ),
    )
    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useInheritBranchAvatar('b3'), { wrapper })

    await expect(result.current.mutateAsync()).rejects.toThrow()
  })
})