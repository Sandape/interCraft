/**
 * REQ-061 (US1) — Monotonic milestone list (server order preserved).
 */
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'
import type { Milestone } from '@/types/ai-runtime'

const MILESTONE_STATUS_LABELS: Record<Milestone['status'], string> = {
  pending: '待开始',
  running: '进行中',
  delivered: '已交付',
  failed: '失败',
  cancelled: '已取消',
  invalidated: '已失效',
}

const MILESTONE_STATUS_VARIANT: Record<
  Milestone['status'],
  'default' | 'brand' | 'success' | 'warning' | 'danger' | 'outline'
> = {
  pending: 'outline',
  running: 'brand',
  delivered: 'success',
  failed: 'danger',
  cancelled: 'outline',
  invalidated: 'default',
}

export interface AIMilestoneListProps {
  milestones: Milestone[]
  className?: string
  emptyLabel?: string
}

export function AIMilestoneList({
  milestones,
  className,
  emptyLabel = '暂无里程碑',
}: AIMilestoneListProps) {
  if (milestones.length === 0) {
    return (
      <p
        className={cn('text-sm text-ink-3 dark:text-dark-ink-tertiary', className)}
        data-testid="ai-milestone-list-empty"
      >
        {emptyLabel}
      </p>
    )
  }

  return (
    <ol
      className={cn('space-y-2', className)}
      data-testid="ai-milestone-list"
    >
      {milestones.map((milestone, index) => (
        <li
          key={milestone.code}
          className="flex items-start gap-3 rounded border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface px-3 py-2"
          data-testid={`ai-milestone-${milestone.code}`}
          data-status={milestone.status}
          data-milestone-code={milestone.code}
        >
          <span
            className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-surface-muted dark:bg-dark-surface-muted text-2xs font-medium text-ink-3 dark:text-dark-ink-tertiary"
            aria-hidden
          >
            {index + 1}
          </span>
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-ink-1 dark:text-dark-ink-primary">
                {milestone.label}
              </span>
              <Badge variant={MILESTONE_STATUS_VARIANT[milestone.status]}>
                {MILESTONE_STATUS_LABELS[milestone.status] ?? milestone.status}
              </Badge>
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-ink-3 dark:text-dark-ink-tertiary">
              <span>
                点数 {milestone.points_settled}
                {milestone.settle_eligible ? ' · 可结算' : ''}
              </span>
              {milestone.delivered_at && (
                <span>
                  交付于 {new Date(milestone.delivered_at).toLocaleString('zh-CN')}
                </span>
              )}
              {milestone.result_ref && (
                <span className="truncate" title={milestone.result_ref}>
                  结果 {milestone.result_ref}
                </span>
              )}
            </div>
          </div>
        </li>
      ))}
    </ol>
  )
}
