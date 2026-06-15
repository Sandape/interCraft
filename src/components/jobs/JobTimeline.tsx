import { Clock } from 'lucide-react'
import { JobStatusBadge } from './StatusBadge'
import type { JobTimelineEntry } from '@/repositories/JobRepository'

export function JobTimeline({ entries }: { entries: JobTimelineEntry[] }) {
  if (!entries || entries.length === 0) {
    return <p className="text-xs text-ink-3 py-4 text-center">暂无状态变更记录</p>
  }

  return (
    <div className="space-y-3">
      {entries.map((entry, i) => (
        <div key={i} className="flex items-start gap-3">
          <div className="flex flex-col items-center mt-0.5">
            <div className="h-2 w-2 rounded-full bg-brand-500 ring-2 ring-brand-100 dark:ring-brand-900" />
            {i < entries.length - 1 && <div className="w-px h-full min-h-[20px] bg-surface-border dark:bg-dark-surface-border mt-1" />}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <JobStatusBadge status={entry.to_status} />
              {entry.from_status && (
                <>
                  <span className="text-ink-muted text-2xs">←</span>
                  <JobStatusBadge status={entry.from_status} />
                </>
              )}
            </div>
            <div className="flex items-center gap-1 mt-1 text-2xs text-ink-3">
              <Clock className="h-2.5 w-2.5" />
              <span>{new Date(entry.changed_at).toLocaleString('zh-CN')}</span>
            </div>
            {entry.note && <p className="text-xs text-ink-2 mt-1">{entry.note}</p>}
          </div>
        </div>
      ))}
    </div>
  )
}
