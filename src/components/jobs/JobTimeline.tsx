import { Calendar, Clock } from 'lucide-react'
import { JobStatusBadge } from './StatusBadge'
import type { JobTimelineEntry } from '@/repositories/JobRepository'

/**
 * REQ-053 (T028) — Timeline still renders the same shape; the badge inside
 * now uses the new 7-state label map (see StatusBadge). Notes surface a hint
 * that the next action is to wait until the auto research fires.
 */
export function JobTimeline({ entries }: { entries: JobTimelineEntry[] }) {
  if (!entries || entries.length === 0) {
    return <p className="text-xs text-ink-3 py-4 text-center">暂无状态变更记录</p>
  }

  // REQ-053 hotfix: backend actually returns `from` / `to` / `changed_at`
  // but the JobTimelineEntry type (master) declares `from_status` / `to_status`.
  // Accept both so the timeline renders regardless of which schema is in flight.
  return (
    <div className="space-y-3">
      {entries.map((entry, i) => {
        const toStatus = (entry as any).to_status ?? entry.to
        const fromStatus = (entry as any).from_status ?? entry.from
        const changedAt = entry.changed_at ?? (entry as any).at
        return (
        <div key={i} className="flex items-start gap-3">
          <div className="flex flex-col items-center mt-0.5">
            <div className="h-2 w-2 rounded-full bg-brand-500 ring-2 ring-brand-100 dark:ring-brand-900" />
            {i < entries.length - 1 && (
              <div className="w-px h-full min-h-[20px] bg-surface-border dark:bg-dark-surface-border mt-1" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <JobStatusBadge status={toStatus} />
              {fromStatus && (
                <>
                  <span className="text-ink-muted text-2xs">←</span>
                  <JobStatusBadge status={fromStatus} />
                </>
              )}
            </div>
            <div className="flex items-center gap-1 mt-1 text-2xs text-ink-3">
              <Clock className="h-2.5 w-2.5" />
              <span>{new Date(changedAt).toLocaleString('zh-CN')}</span>
            </div>
            {entry.note && <p className="text-xs text-ink-2 mt-1">{entry.note}</p>}
          </div>
        </div>
        )
      })}
    </div>
  )
}

/**
 * REQ-053 (T028) — Renders the job's `interview_time` in a compact row
 * designed to live next to the status badge. Empty state is explicit so the
 * user knows the field is actionable, not missing.
 */
export function InterviewTimeRow({ interviewTime }: { interviewTime: string | null }) {
  if (!interviewTime) {
    return (
      <div
        data-testid="interview-time-empty"
        className="flex items-center gap-2 text-2xs text-ink-3"
      >
        <Calendar className="h-3 w-3" />
        <span>未设置面试时间</span>
      </div>
    )
  }
  const date = new Date(interviewTime)
  return (
    <div
      data-testid="interview-time-row"
      className="flex items-center gap-2 text-xs text-ink-1"
    >
      <Calendar className="h-3 w-3 text-brand-500" />
      <span className="font-medium">面试时间</span>
      <span data-testid="interview-time-value">{date.toLocaleString('zh-CN')}</span>
    </div>
  )
}
