/**
 * @vitest-environment jsdom
 * REQ-061 T093 — separate score/insight states, research quote/tier/sources.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AbilityProfile from '@/pages/AbilityProfile'
import { InterviewResearchControl } from '@/components/interview/InterviewResearchControl'

vi.mock('@/pages/AbilityProfile/hooks/queries/useAbilityProfile', () => ({
  useAbilityDashboard: () => ({
    data: {
      data: {
        dimensions: [
          {
            key: 'tech',
            label_zh: '技术深度',
            actual_score: 7.5,
            ideal_score: 9,
            self_assessed_score: null,
            source: 'interview',
            trend: 'up',
            history: [],
          },
        ],
        generated_at: '2026-07-11T00:00:00Z',
        ai_insight: {
          task_id: 'task-insight-1',
          status: 'failed',
          user_summary: '洞察生成失败，已验证评分不受影响。',
          available_actions: ['system_failure_retry'],
          failure_category: 'insight_generation_failed',
        },
        verified_score_status: 'ready',
      },
    },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
}))

vi.mock('@/pages/AbilityProfile/hooks/mutations/useSelfAssess', () => ({
  useSelfAssess: () => ({ mutate: vi.fn() }),
}))

vi.mock('@/pages/AbilityProfile/hooks/mutations/useExportPDF', () => ({
  useExportPdf: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('@/pages/AbilityProfile/RadarChart', () => ({
  default: () => <div data-testid="radar" />,
}))

vi.mock('@/pages/AbilityProfile/AbilityCard', () => ({
  default: () => <div data-testid="ability-card" />,
}))

vi.mock('@/pages/AbilityProfile/AbilityDetail', () => ({
  default: () => null,
}))

vi.mock('@/pages/AbilityProfile/ShareDialog', () => ({
  default: () => null,
}))

function wrap(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AIInsightResearch (REQ-061 T093)', () => {
  it('separates verified score from AI insight failure with retry/task links', () => {
    wrap(<AbilityProfile />)
    expect(screen.getByTestId('verified-score-panel')).toBeInTheDocument()
    expect(screen.getByTestId('ai-insight-panel')).toBeInTheDocument()
    expect(screen.getByTestId('ai-insight-panel').textContent).toMatch(/洞察生成失败/)
    expect(screen.getByTestId('ai-insight-task-link')).toHaveAttribute('href', '/ai-tasks/task-insight-1')
  })

  it('research control shows quote/tier preview, disable, sources, and failed delivery', () => {
    const onCancel = vi.fn()
    wrap(
      <InterviewResearchControl
        sessionId="s1"
        enabled={true}
        quote={{ service_tier: 'standard', point_cap: 40, quoted_max: 40 }}
        sources={[{ title: '公司面经', url: 'https://example.com/a' }]}
        status="failed"
        taskId="task-research-1"
        failureMessage="研究交付失败，未扣点。"
        onOptIn={vi.fn()}
        onDisable={vi.fn()}
        onCancel={onCancel}
      />,
    )
    expect(screen.getByTestId('research-point-preview').textContent).toMatch(/40/)
    expect(screen.getByTestId('research-tier').textContent).toMatch(/标准|standard/i)
    expect(screen.getByTestId('research-source')).toBeInTheDocument()
    expect(screen.getByTestId('research-failure').textContent).toMatch(/未扣点/)
    fireEvent.click(screen.getByTestId('research-cancel'))
    expect(onCancel).toHaveBeenCalled()
  })
})
