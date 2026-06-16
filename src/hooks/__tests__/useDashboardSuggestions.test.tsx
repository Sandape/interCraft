/** 018 #2 — useDashboardSuggestions tier boundaries. */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const branchesMock = vi.fn()
const errorQuestionsMock = vi.fn()
const jobsMock = vi.fn()
const interviewSessionsMock = vi.fn()

vi.mock('@/hooks/queries/useResumeBranches', () => ({
  useResumeBranches: () => ({ data: branchesMock() }),
}))
vi.mock('@/hooks/queries/useErrorQuestions', () => ({
  useErrorQuestions: () => ({ data: errorQuestionsMock() }),
}))
vi.mock('@/hooks/queries/useJobs', () => ({
  useJobs: () => ({ data: jobsMock() }),
}))
vi.mock('@/hooks/queries/useInterviewSessions', () => ({
  useInterviewSessions: () => ({ data: interviewSessionsMock() }),
}))

import { useDashboardSuggestions } from '@/hooks/useDashboardSuggestions'

beforeEach(() => {
  branchesMock.mockReset()
  errorQuestionsMock.mockReset()
  jobsMock.mockReset()
  interviewSessionsMock.mockReset()
})

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('useDashboardSuggestions — tiers (018 #2)', () => {
  it('returns tier 0 when there are no completed interviews', () => {
    branchesMock.mockReturnValue([])
    errorQuestionsMock.mockReturnValue({ data: [] })
    jobsMock.mockReturnValue({ data: [] })
    interviewSessionsMock.mockReturnValue({ data: [] })

    const { result } = renderHook(() => useDashboardSuggestions(), { wrapper })
    expect(result.current.tier).toBe(0)
    expect(result.current.blocks[0].id).toBe('cta-first-interview')
    expect(result.current.blocks[0].cta?.href).toBe('/interview/new')
  })

  it('returns tier 1 when at least one interview is completed but other data is missing', () => {
    branchesMock.mockReturnValue([])
    errorQuestionsMock.mockReturnValue({ data: [] })
    jobsMock.mockReturnValue({ data: [] })
    interviewSessionsMock.mockReturnValue({
      data: [
        {
          id: 's1',
          status: 'completed',
          company: '字节跳动',
          position: '前端工程师',
          overall_score: 7.5,
          ended_at: '2026-06-10T12:00:00Z',
        },
      ],
    })

    const { result } = renderHook(() => useDashboardSuggestions(), { wrapper })
    expect(result.current.tier).toBe(1)
    const ids = result.current.blocks.map((b) => b.id)
    expect(ids).toContain('recap-latest-interview')
    expect(ids).toContain('cta-create-resume')
    expect(ids).toContain('cta-add-error-question')
    expect(ids).toContain('cta-add-job')
  })

  it('returns tier 2 when interviews, resume, errors and jobs all exist', () => {
    branchesMock.mockReturnValue([
      { id: 'b1', name: '主简历', is_main: true },
      { id: 'b2', name: '字节前端' },
    ])
    errorQuestionsMock.mockReturnValue({ data: [{ id: 'e1' }, { id: 'e2' }, { id: 'e3' }] })
    jobsMock.mockReturnValue({ data: [{ id: 'j1' }, { id: 'j2' }] })
    interviewSessionsMock.mockReturnValue({
      data: [
        { id: 's1', status: 'completed', ended_at: '2026-06-01T00:00:00Z' },
        { id: 's2', status: 'completed', ended_at: '2026-06-05T00:00:00Z' },
        { id: 's3', status: 'completed', ended_at: '2026-06-09T00:00:00Z' },
      ],
    })

    const { result } = renderHook(() => useDashboardSuggestions(), { wrapper })
    expect(result.current.tier).toBe(2)
    const ids = result.current.blocks.map((b) => b.id)
    expect(ids).toContain('global-ability-trend')
    expect(ids).toContain('global-resume-refine')
    expect(ids).toContain('global-error-coach')
  })

  it('tier 1 latest recap surfaces the actual company / position / score from data', () => {
    branchesMock.mockReturnValue([])
    errorQuestionsMock.mockReturnValue({ data: [] })
    jobsMock.mockReturnValue({ data: [] })
    interviewSessionsMock.mockReturnValue({
      data: [
        {
          id: 's1',
          status: 'completed',
          company: '字节跳动',
          position: '前端',
          overall_score: 6.2,
          ended_at: '2026-06-09T00:00:00Z',
        },
      ],
    })

    const { result } = renderHook(() => useDashboardSuggestions(), { wrapper })
    const recap = result.current.blocks.find((b) => b.id === 'recap-latest-interview')
    expect(recap?.title).toContain('字节跳动')
    expect(recap?.title).toContain('前端')
    expect(recap?.body).toContain('6.2')
  })

  it('does NOT contain legacy fake-data literals anywhere in any tier output', () => {
    const OFFENDING = ['+13', '+14', '+15', '系统设计失分 3 次', '字节跳动简历分支']
    branchesMock.mockReturnValue([])
    errorQuestionsMock.mockReturnValue({ data: [] })
    jobsMock.mockReturnValue({ data: [] })
    interviewSessionsMock.mockReturnValue({
      data: [
        { id: 's1', status: 'completed', company: '字节跳动', position: '前端', ended_at: '2026-06-09T00:00:00Z' },
      ],
    })
    const { result } = renderHook(() => useDashboardSuggestions(), { wrapper })
    const haystack = result.current.blocks
      .flatMap((b) => [b.title, b.body, b.cta?.label ?? '', b.cta?.href ?? ''])
      .join(' ')
    for (const phrase of OFFENDING) {
      expect(haystack.includes(phrase), `must not contain "${phrase}"`).toBe(false)
    }
  })
})