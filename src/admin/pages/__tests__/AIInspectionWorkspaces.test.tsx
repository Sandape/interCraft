/**
 * REQ-061 T157 — AI inspection workspaces (soft frontend tests).
 */
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/hooks/queries/useCurrentUser', () => ({
  useCurrentUser: () => ({ data: { is_admin: true }, isLoading: false }),
}))

vi.mock('@/stores/useAuthStore', () => ({
  useAuthStore: (sel: (s: { user: { email: string; is_admin: boolean } }) => unknown) =>
    sel({ user: { email: 'admin@test.local', is_admin: true } }),
}))

vi.mock('@/admin/pages/CommandCenter', () => ({ CommandCenter: () => <div>指挥中心</div> }))
vi.mock('@/admin/pages/ProductAnalytics', () => ({ ProductAnalytics: () => <div>产品分析</div> }))
vi.mock('@/admin/pages/AIOperations', () => ({ AIOperations: () => <div data-testid="ai-ops">AI 运营</div> }))
vi.mock('@/admin/pages/IncidentsBadcases', () => ({
  IncidentsBadcases: () => <div data-testid="incidents">事件与差例</div>,
}))
vi.mock('@/admin/pages/LogsAndTraces', () => ({
  LogsAndTraces: () => <div data-testid="logs-traces">日志与链路</div>,
}))
vi.mock('@/admin/pages/UsersAccounts', () => ({ UsersAccounts: () => <div>用户</div> }))
vi.mock('@/admin/pages/Reports', () => ({ Reports: () => <div>报告</div> }))
vi.mock('@/admin/pages/Governance', () => ({
  Governance: () => <div data-testid="governance">治理与审计</div>,
}))
vi.mock('@/admin/pages/AIReleaseGovernance', () => ({
  AIReleaseGovernance: () => <div>AI 发布</div>,
}))
vi.mock('@/admin/pages/ModelPolicies', () => ({
  ModelPolicies: () => <div>模型策略</div>,
}))

import { AdminShell, ADMIN_ROUTE_CONFIG } from '@/admin/components/AdminShell'

const FOUR_WORKSPACES = [
  '/admin-console/ai-operations',
  '/admin-console/incidents-badcases',
  '/admin-console/logs-and-traces',
  '/admin-console/governance',
]

describe('AIInspectionWorkspaces (soft)', () => {
  it('preserves four inspection workspace routes', () => {
    const paths = ADMIN_ROUTE_CONFIG.flatMap((r) =>
      (r.children ?? []).map((c: { path?: string }) => c.path),
    )
    for (const ws of ['ai-operations', 'incidents-badcases', 'logs-and-traces', 'governance']) {
      expect(paths).toContain(ws)
    }
  })

  it('renders stable deep-link shells for inspection workspaces', () => {
    for (const path of FOUR_WORKSPACES) {
      const { unmount } = render(
        <MemoryRouter initialEntries={[path]}>
          <AdminShell />
        </MemoryRouter>,
      )
      expect(document.querySelector('.ac-shell')).toBeTruthy()
      unmount()
    }
  })

  it('shows AI operations nav when admin', () => {
    render(
      <MemoryRouter initialEntries={['/admin-console/ai-operations']}>
        <AdminShell />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('ai-ops')).toBeTruthy()
    expect(screen.getAllByText('AI 运营').length).toBeGreaterThanOrEqual(1)
  })
})
