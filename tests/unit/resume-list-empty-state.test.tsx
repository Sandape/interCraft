/**
 * 036 REQ-036 US5 T041 — ResumeList empty-state unit tests.
 *
 * Verifies the empty-state surface added in Phase B:
 *   - CTA button "创建你的第一份简历" (data-testid="empty-state-cta")
 *   - 3 recommended template thumbnails:
 *     pikachu, onyx, bronzor (data-testid="recommended-template-{id}")
 *   - Clicking CTA opens the Template Gallery modal
 *   - Clicking a thumbnail opens the modal (with the template pre-selected
 *     — we only verify the modal opens; prefill UX is owned by the modal)
 *   - When the list is non-empty, the empty-state surface does NOT render
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ResumeList from '@/pages/ResumeList'
import { useAuthStore } from '@/stores/useAuthStore'

const v2ListMock = vi.fn().mockResolvedValue({ data: [] })
vi.mock('@/modules/resume/v2/api', () => ({
  listResumes: (...args: unknown[]) => v2ListMock(...args),
}))

beforeEach(() => {
  v2ListMock.mockReset()
  v2ListMock.mockResolvedValue({ data: [] })
  useAuthStore.setState({
    user: {
      id: '01900000-0000-7000-8000-000000000001',
      email: 'demo@intercraft.io',
      display_name: 'Demo',
      title: '前端工程师',
      years_of_experience: 3,
      target_role: '高级前端',
      bio: null,
      avatar_url: null,
      subscription: 'free',
      created_at: '2026-06-01T00:00:00Z',
      updated_at: '2026-06-12T00:00:00Z',
    },
  })
})

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/resume" element={<ResumeList />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('US5 T041 — ResumeList empty-state (036 Phase B)', () => {
  it('空状态 CTA "创建你的第一份简历" 渲染', async () => {
    renderAt('/resume')
    await waitFor(() => {
      expect(screen.getByTestId('empty-state-cta')).toBeInTheDocument()
    })
    expect(screen.getByTestId('empty-state-cta').textContent).toContain('创建你的第一份简历')
  })

  it('空状态显示 3 个推荐模板缩略图 (pikachu / onyx / bronzor)', async () => {
    renderAt('/resume')
    await waitFor(() => {
      expect(screen.getByTestId('recommended-template-pikachu')).toBeInTheDocument()
    })
    expect(screen.getByTestId('recommended-template-onyx')).toBeInTheDocument()
    expect(screen.getByTestId('recommended-template-bronzor')).toBeInTheDocument()
    // Total thumbnails count = 3 (no extras)
    expect(screen.getAllByTestId(/^recommended-template-/)).toHaveLength(3)
  })

  it('点 CTA → 打开 Template Gallery modal', async () => {
    renderAt('/resume')
    await waitFor(() => {
      expect(screen.getByTestId('empty-state-cta')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('empty-state-cta'))
    await waitFor(() => {
      expect(screen.getByTestId('template-gallery-grid')).toBeInTheDocument()
    })
  })

  it('点推荐模板缩略图 → 打开 Template Gallery modal', async () => {
    renderAt('/resume')
    await waitFor(() => {
      expect(screen.getByTestId('recommended-template-pikachu')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('recommended-template-pikachu'))
    await waitFor(() => {
      expect(screen.getByTestId('template-gallery-grid')).toBeInTheDocument()
    })
  })

  it('列表非空时,空状态 CTA 不渲染', async () => {
    v2ListMock.mockResolvedValueOnce({
      data: [
        {
          id: 'r-1',
          name: '主简历',
          slug: 'main',
          template: 'pikachu',
          version: 1,
          is_public: false,
          updated_at: '2026-06-12T00:00:00Z',
          created_at: '2026-06-01T00:00:00Z',
        },
      ],
    })
    renderAt('/resume')
    await waitFor(() => {
      expect(screen.getByTestId('v2-resume-card')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('empty-state-cta')).not.toBeInTheDocument()
    expect(screen.queryByTestId('recommended-template-pikachu')).not.toBeInTheDocument()
  })
})