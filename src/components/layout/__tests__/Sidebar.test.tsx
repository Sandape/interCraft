/** 036 Phase A.2 (US1) — Sidebar 收口验证。
 *  REQ-036 Phase A.2:
 *   - 单条 "简历中心" 主入口（v1 分支树已下线）
 *   - 没有 v2 简历副本（v1 "v2 简历" 入口已下线）
 *   - 主导航里没有 /resume-v2 / /resume/v2 链接 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Sidebar } from '@/components/layout/Sidebar'
import { useAuthStore } from '@/stores/useAuthStore'

const mockUseResumeV2List = vi.fn().mockReturnValue({ data: [] })
vi.mock('@/hooks/queries/useResumeV2List', () => ({
  useResumeV2List: () => mockUseResumeV2List(),
}))

beforeEach(() => {
  mockUseResumeV2List.mockReturnValue({ data: [] })
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
      is_admin: true,
      created_at: '2026-06-01T00:00:00Z',
      updated_at: '2026-06-12T00:00:00Z',
    },
  })
})

function renderSidebar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/dashboard']}>
        <Sidebar collapsed={false} onToggle={vi.fn()} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Sidebar — single resume entry (036 Phase A.2 US1)', () => {
  it('renders exactly one 简历中心 primary nav link (no v1 branch tree, no v2 copy)', () => {
    renderSidebar()
    const allLinks = screen.getAllByRole('link')
    const resumeLinks = allLinks.filter((a) => {
      const href = a.getAttribute('href') ?? ''
      return href === '/resume'
    })
    expect(resumeLinks).toHaveLength(1)
  })

  it('does NOT expose any /resume-v2 or /resume/v2/* links', () => {
    renderSidebar()
    const allLinks = screen.getAllByRole('link')
    for (const a of allLinks) {
      const href = a.getAttribute('href') ?? ''
      expect(href.startsWith('/resume-v2')).toBe(false)
      expect(href.startsWith('/resume/v2')).toBe(false)
    }
  })

  it('shows the v2 resume count badge on the single resume entry', () => {
    mockUseResumeV2List.mockReturnValue({ data: [{ id: 'r1' }, { id: 'r2' }, { id: 'r3' }] })
    renderSidebar()
    // The NavLink with /resume href should display badge "3"
    const allLinks = screen.getAllByRole('link')
    const resumeLink = allLinks.find((a) => a.getAttribute('href') === '/resume')
    expect(resumeLink).toBeDefined()
    expect(resumeLink?.textContent).toContain('3')
  })
})