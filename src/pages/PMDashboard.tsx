/** REQ-033 US1 T077 + US2 T089 + US3 T098 — PMDashboard page shell.
 *
 * Layout:
 * - Header: page title + date range picker + environment selector.
 * - Four-panel grid: Overview (top) + Funnel (middle) +
 *   Resume Diagnosis (US2 T089) + Mock Interview (US3 T098).
 * - Loading skeleton while data is in flight.
 * - Error state with a retry hint.
 * - Date range / environment changes re-fetch via TanStack Query.
 */
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Calendar, Filter, Loader2 } from 'lucide-react'
import { pmDashboardApi } from '@/api/pm-dashboard'
import { OverviewPanel } from '@/components/pm-dashboard/OverviewPanel'
import { FunnelPanel } from '@/components/pm-dashboard/FunnelPanel'
import { ResumeDiagnosisPanel } from '@/components/pm-dashboard/ResumeDiagnosisPanel'
import { MockInterviewPanel } from '@/components/pm-dashboard/MockInterviewPanel'
import type { DashboardFilter } from '@/types/pm-dashboard'

function ymd(d: Date): string {
  const y = d.getUTCFullYear()
  const m = String(d.getUTCMonth() + 1).padStart(2, '0')
  const day = String(d.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function toIsoStart(date: string): string {
  // Treat the date as UTC midnight for stable comparison.
  return `${date}T00:00:00.000Z`
}

function toIsoEnd(date: string): string {
  // Exclusive end at next-day UTC midnight.
  const next = new Date(`${date}T00:00:00.000Z`)
  next.setUTCDate(next.getUTCDate() + 1)
  return next.toISOString()
}

const ENV_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '', label: '全部环境' },
  { value: 'production', label: '生产' },
  { value: 'staging', label: '预发' },
  { value: 'ci', label: 'CI' },
  { value: 'local', label: '本地' },
]

export default function PMDashboard() {
  // Default range: last 7 days, ending today (UTC).
  const today = useMemo(() => ymd(new Date()), [])
  const sevenAgo = useMemo(() => {
    const d = new Date()
    d.setUTCDate(d.getUTCDate() - 7)
    return ymd(d)
  }, [])

  const [dateFrom, setDateFrom] = useState(sevenAgo)
  const [dateTo, setDateTo] = useState(today)
  const [environment, setEnvironment] = useState('')

  const filter: DashboardFilter = useMemo(
    () => ({
      date_range_start: toIsoStart(dateFrom),
      date_range_end: toIsoEnd(dateTo),
      environment: (environment || undefined) as DashboardFilter['environment'],
    }),
    [dateFrom, dateTo, environment],
  )

  const overviewQuery = useQuery({
    queryKey: ['pm-dashboard', 'overview', filter],
    queryFn: () => pmDashboardApi.getOverview(filter),
    staleTime: 30_000,
  })
  const funnelQuery = useQuery({
    queryKey: ['pm-dashboard', 'funnel', filter],
    queryFn: () => pmDashboardApi.getFunnel(filter),
    staleTime: 30_000,
  })
  const resumeQuery = useQuery({
    queryKey: ['pm-dashboard', 'resume-diagnosis', filter],
    queryFn: () => pmDashboardApi.getResumeDiagnosis(filter),
    staleTime: 30_000,
  })
  const mockInterviewQuery = useQuery({
    queryKey: ['pm-dashboard', 'mock-interview', filter],
    queryFn: () => pmDashboardApi.getMockInterview(filter),
    staleTime: 30_000,
  })

  const isLoading =
    overviewQuery.isLoading ||
    funnelQuery.isLoading ||
    resumeQuery.isLoading ||
    mockInterviewQuery.isLoading
  const error =
    overviewQuery.error ||
    funnelQuery.error ||
    resumeQuery.error ||
    mockInterviewQuery.error

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="pm-dashboard-page">
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-ink-1">PM 看板 V1</h1>
        <p className="text-sm text-ink-3 mt-1">
          产品概览与核心漏斗 — 内部 PM 使用,数据来源 InterCraft-controlled 事件/AI 记录。
        </p>
      </header>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface p-3">
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-ink-3" />
          <label className="text-xs text-ink-3">起始</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            data-testid="pm-date-from"
            className="text-xs rounded border border-surface-border bg-surface px-2 py-1"
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-ink-3">结束</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            data-testid="pm-date-to"
            className="text-xs rounded border border-surface-border bg-surface px-2 py-1"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-ink-3" />
          <label className="text-xs text-ink-3">环境</label>
          <select
            value={environment}
            onChange={(e) => setEnvironment(e.target.value)}
            data-testid="pm-env-selector"
            className="text-xs rounded border border-surface-border bg-surface px-2 py-1"
          >
            {ENV_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div
          className="rounded-md border border-surface-border bg-surface-muted dark:bg-dark-surface-muted p-8 flex items-center justify-center text-sm text-ink-3"
          data-testid="pm-skeleton"
        >
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
          正在加载 PM 数据...
        </div>
      )}

      {/* Error state */}
      {error && !isLoading && (
        <div
          className="rounded-md border border-red-300 bg-red-50 dark:bg-red-950/30 p-4 text-sm text-red-700 dark:text-red-300"
          data-testid="pm-error"
        >
          <div className="font-medium mb-1">数据加载失败</div>
          <div className="text-xs">
            {error instanceof Error ? error.message : '未知错误'}
          </div>
        </div>
      )}

      {/* Panels */}
      {!isLoading && !error && overviewQuery.data && (
        <div className="space-y-4">
          <OverviewPanel panel={overviewQuery.data} />
          {funnelQuery.data && <FunnelPanel panel={funnelQuery.data} />}
          {resumeQuery.data && (
            <ResumeDiagnosisPanel panel={resumeQuery.data} />
          )}
          {mockInterviewQuery.data && (
            <MockInterviewPanel panel={mockInterviewQuery.data} />
          )}
        </div>
      )}
    </div>
  )
}