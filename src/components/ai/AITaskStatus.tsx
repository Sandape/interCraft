/**
 * REQ-061 (US1) — Canonical AI task status / stage / actions / point summary.
 *
 * Accepts a TaskSummary/TaskDetail-shaped `task` so terminal and
 * available_actions stay server-derived (never inferred from status).
 */
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'
import type {
  AvailableAction,
  PointSummary,
  TaskDetail,
  TaskStatus,
  TaskSummary,
} from '@/types/ai-runtime'

const STATUS_LABELS: Record<TaskStatus, string> = {
  accepted: '已受理',
  queued: '排队中',
  running: '运行中',
  waiting_user: '等待你操作',
  retry_wait: '等待重试',
  cancelling: '取消中',
  result_confirming: '结果确认中',
  succeeded: '已成功',
  partially_succeeded: '部分成功',
  failed: '已失败',
  cancelled: '已取消',
  expired: '已过期',
}

const STATUS_VARIANT: Record<
  TaskStatus,
  'default' | 'brand' | 'success' | 'warning' | 'danger' | 'outline'
> = {
  accepted: 'brand',
  queued: 'default',
  running: 'brand',
  waiting_user: 'warning',
  retry_wait: 'warning',
  cancelling: 'warning',
  result_confirming: 'brand',
  succeeded: 'success',
  partially_succeeded: 'warning',
  failed: 'danger',
  cancelled: 'outline',
  expired: 'outline',
}

const ACTION_LABELS: Record<AvailableAction, string> = {
  open_result: '查看结果',
  provide_input: '补充输入',
  confirm: '确认',
  cancel: '取消',
  resume: '继续',
  retry_failed_component: '重试失败部分',
  system_failure_retry: '系统失败重试',
  reexecute: '重新执行',
  submit_feedback: '提交反馈',
  dispute_points: '点数异议',
}

const SETTLEMENT_LABELS: Record<PointSummary['settlement_status'], string> = {
  unsettled: '未结算',
  zero: '零扣费',
  partial: '部分结算',
  full: '已结清',
  reversed: '已冲正',
}

export function aiTaskStatusLabel(status: TaskStatus): string {
  return STATUS_LABELS[status] ?? status
}

export function aiAvailableActionLabel(action: AvailableAction): string {
  return ACTION_LABELS[action] ?? action
}

export type AITaskStatusTask = Pick<
  TaskSummary | TaskDetail,
  'status' | 'stage' | 'terminal' | 'available_actions' | 'point_summary'
>

export interface AITaskStatusProps {
  task: AITaskStatusTask
  className?: string
  /** Optional click handler for an available action chip (wired by T043). */
  onAction?: (action: AvailableAction) => void
}

export function AITaskStatus({ task, className, onAction }: AITaskStatusProps) {
  const { status, stage, terminal, available_actions, point_summary } = task
  const progress =
    typeof stage.progress_percent === 'number' ? stage.progress_percent : null

  return (
    <div
      className={cn('space-y-3', className)}
      data-testid="ai-task-status"
      data-terminal={terminal ? 'true' : 'false'}
      data-status={status}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          variant={STATUS_VARIANT[status] ?? 'default'}
          data-testid="ai-task-status-badge"
        >
          {aiTaskStatusLabel(status)}
        </Badge>
        {terminal && (
          <Badge variant="outline" data-testid="ai-task-terminal-badge">
            已结束
          </Badge>
        )}
        <span
          className="text-sm text-ink-2 dark:text-dark-ink-secondary"
          data-testid="ai-task-stage"
          data-stage-code={stage.code}
        >
          {stage.label}
        </span>
      </div>

      {progress !== null && (
        <div
          className="h-1.5 w-full overflow-hidden rounded bg-surface-muted dark:bg-dark-surface-muted"
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
          data-testid="ai-task-progress"
        >
          <div
            className="h-full rounded bg-brand-500 transition-[width] duration-300"
            style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
          />
        </div>
      )}

      {point_summary && (
        <div
          className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-3 dark:text-dark-ink-tertiary"
          data-testid="ai-task-point-summary"
          data-settlement={point_summary.settlement_status}
        >
          <span>上限 {point_summary.quoted_max}</span>
          <span>预留 {point_summary.reserved}</span>
          <span>已扣 {point_summary.settled}</span>
          <span>已释放 {point_summary.released}</span>
          <span>
            结算{' '}
            {SETTLEMENT_LABELS[point_summary.settlement_status] ??
              point_summary.settlement_status}
          </span>
        </div>
      )}

      {available_actions.length > 0 && (
        <div
          className="flex flex-wrap gap-1.5"
          data-testid="ai-task-available-actions"
        >
          {available_actions.map((action) => (
            <button
              key={action}
              type="button"
              data-testid={`ai-task-action-${action}`}
              data-action={action}
              disabled={!onAction}
              onClick={() => onAction?.(action)}
              className={cn(
                'rounded border border-surface-border dark:border-dark-surface-border',
                'px-2 py-1 text-xs text-ink-2 dark:text-dark-ink-secondary',
                onAction
                  ? 'hover:bg-surface-muted dark:hover:bg-dark-surface-muted cursor-pointer'
                  : 'cursor-default opacity-80',
              )}
            >
              {aiAvailableActionLabel(action)}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
