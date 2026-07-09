/**
 * REQ-057 — Dashboard command-center summary (single first-screen source).
 */
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { request } from '@/api/client'

export const DASHBOARD_SUMMARY_KEY = ['me', 'dashboard-summary'] as const

export interface DashboardCta {
  label: string
  href: string
}

export interface TodayInterviewItem {
  job_id: string
  company: string
  position: string
  interview_time: string
  status: string
  relative_label: string
  href: string
}

export interface OnboardingStep {
  id: 'resume' | 'job' | 'interview'
  done: boolean
  href: string
}

export interface DashboardSummary {
  generated_at: string
  cache_ttl_sec: number
  tz: string
  local_date: string
  l0: {
    greeting_context: string
    next_interview: TodayInterviewItem | null
    today_interviews: TodayInterviewItem[]
    primary_cta: DashboardCta
    onboarding: { show: boolean; steps: OnboardingStep[] } | null
    resumable_sessions: Array<{
      session_id: string
      company: string | null
      position: string | null
      status: string
      href: string
    }>
  }
  l1: {
    resume_summaries: Array<{
      id: string
      name: string
      resume_kind: string
      job_id: string | null
      updated_at: string | null
      href: string
    }>
    resume_counts: { root: number; derived: number; standard: number; total: number }
    next_action: {
      id: string
      title_zh: string
      body_zh: string
      cta: DashboardCta
      tier: 0 | 1 | 2
    } | null
    job_funnel: Array<{
      key: 'applying' | 'interviewing' | 'awaiting_feedback'
      label_zh: string
      count: number
      filter_statuses: string[]
      href: string
    }>
    prep_pack: {
      job_id: string
      derived_resume_id: string | null
      actions: DashboardCta[]
    } | null
  }
  l2: {
    ability_snapshot: {
      overall_score: number
      weakest_dimensions: Array<{ key: string; label_zh: string; actual_score: number }>
      href: string
    } | null
    recent_activities: Array<{
      id: string
      type: string
      title_zh: string
      detail_zh: string
      occurred_at: string | null
      href: string | null
    }>
    interview_trend: { completed_count: number; avg_score: number } | null
  }
}

function localDateInTz(tz: string): string {
  try {
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: tz,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(new Date())
  } catch {
    return new Date().toISOString().slice(0, 10)
  }
}

export async function fetchDashboardSummary(tz = 'Asia/Shanghai'): Promise<DashboardSummary> {
  const res = await request<{ data: DashboardSummary }>({
    method: 'GET',
    path: '/api/v1/me/dashboard-summary',
    query: { tz },
  })
  return res.data
}

export function useDashboardSummary(opts?: { tz?: string }) {
  const tz = opts?.tz ?? 'Asia/Shanghai'
  const localDate = localDateInTz(tz)
  return useQuery({
    queryKey: [...DASHBOARD_SUMMARY_KEY, localDate, tz],
    queryFn: () => fetchDashboardSummary(tz),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
    refetchOnWindowFocus: true,
  })
}

export function useInvalidateDashboardSummary() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: DASHBOARD_SUMMARY_KEY })
}

export function invalidateDashboardSummary(qc: ReturnType<typeof useQueryClient>) {
  return qc.invalidateQueries({ queryKey: DASHBOARD_SUMMARY_KEY })
}
