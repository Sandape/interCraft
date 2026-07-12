/**
 * REQ-061 (US2) — Server-derived AI task control actions.
 *
 * Renders cancel / resume / system_failure_retry / reexecute only when the
 * server lists them in `available_actions`. Version conflicts trigger a
 * refresh callback so the parent can reload task_version.
 */
import { useCallback, useId, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  cancelAITask,
  resumeAITask,
  retrySystemFailedAITask,
} from '@/api/ai-runtime'
import { ApiError } from '@/api/errors'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { aiAvailableActionLabel } from '@/components/ai/AITaskStatus'
import { AIReexecutionDialog } from '@/components/ai/AIReexecutionDialog'
import { aiTaskKeys } from '@/hooks/queries/useAITasks'
import { cn } from '@/lib/utils'
import type {
  AvailableAction,
  PointSummary,
  TaskAccepted,
  TaskDetail,
} from '@/types/ai-runtime'

const CONTROL_ACTIONS = new Set<AvailableAction>([
  'cancel',
  'resume',
  'system_failure_retry',
  'reexecute',
])

function newIdempotencyKey(prefix: string): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `${prefix}-${crypto.randomUUID()}`
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export type AITaskActionsTask = Pick<
  TaskDetail,
  'task_id' | 'task_version' | 'available_actions' | 'status' | 'terminal' | 'point_summary'
> & {
  capability?: string
  action?: string
  service_tier?: TaskDetail['service_tier']
}

export interface AITaskActionsProps {
  task: AITaskActionsTask
  className?: string
  /** Called after a successful control mutation (parent may navigate). */
  onAccepted?: (result: TaskAccepted, action: AvailableAction) => void
  /** Called on 409 VERSION_CONFLICT so the parent can refetch. */
  onConflictRefresh?: () => void | Promise<void>
  /** Optional point cap preview for re-execution quote. */
  pointPreview?: Pick<PointSummary, 'quoted_max'> | null
}

type ConfirmKind = 'cancel' | 'resume' | 'system_failure_retry' | null

export function AITaskActions({
  task,
  className,
  onAccepted,
  onConflictRefresh,
  pointPreview,
}: AITaskActionsProps) {
  const queryClient = useQueryClient()
  const titleId = useId()
  const [confirm, setConfirm] = useState<ConfirmKind>(null)
  const [reexecOpen, setReexecOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const actions = task.available_actions.filter((a) => CONTROL_ACTIONS.has(a))

  const invalidate = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: aiTaskKeys.detail(task.task_id) })
    await queryClient.invalidateQueries({ queryKey: aiTaskKeys.lists() })
  }, [queryClient, task.task_id])

  const handleConflict = useCallback(
    async (err: unknown) => {
      if (err instanceof ApiError && err.status === 409) {
        const code = err.code
        if (code === 'VERSION_CONFLICT' || code === 'ACTION_NOT_ALLOWED') {
          setError(
            code === 'VERSION_CONFLICT'
              ? '任务已更新，请刷新后重试'
              : '当前状态不允许该操作，请刷新',
          )
          await invalidate()
          await onConflictRefresh?.()
          return true
        }
      }
      return false
    },
    [invalidate, onConflictRefresh],
  )

  const runControl = useCallback(
    async (kind: Exclude<ConfirmKind, null>) => {
      setBusy(true)
      setError(null)
      try {
        const key = newIdempotencyKey(kind)
        const body = { expected_task_version: task.task_version }
        let result: TaskAccepted
        if (kind === 'cancel') {
          result = await cancelAITask(task.task_id, body, key)
        } else if (kind === 'resume') {
          result = await resumeAITask(task.task_id, body, key)
        } else {
          result = await retrySystemFailedAITask(task.task_id, body, key)
        }
        setConfirm(null)
        await invalidate()
        onAccepted?.(result, kind)
      } catch (err) {
        if (await handleConflict(err)) {
          setConfirm(null)
          return
        }
        const message =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : '操作失败'
        setError(message)
      } finally {
        setBusy(false)
      }
    },
    [handleConflict, invalidate, onAccepted, task.task_id, task.task_version],
  )

  if (actions.length === 0) {
    return null
  }

  const confirmCopy: Record<
    Exclude<ConfirmKind, null>,
    { title: string; description: string; confirmLabel: string; danger?: boolean }
  > = {
    cancel: {
      title: '确认取消任务？',
      description: '取消请求会先进入「取消中」，最终状态以服务器确认为准。',
      confirmLabel: '确认取消',
      danger: true,
    },
    resume: {
      title: '从检查点继续？',
      description: '将在可信检查点恢复执行，不会重新计费已完成的里程碑。',
      confirmLabel: '继续执行',
    },
    system_failure_retry: {
      title: '系统失败重试？',
      description: '将在同一计费谱系下创建新的执行，用于瞬时系统故障恢复。',
      confirmLabel: '重试',
    },
  }

  return (
    <div
      className={cn('space-y-2', className)}
      data-testid="ai-task-actions"
      data-task-version={task.task_version}
    >
      <div className="flex flex-wrap gap-2">
        {actions.map((action) => {
          if (action === 'reexecute') {
            return (
              <Button
                key={action}
                type="button"
                size="sm"
                variant="secondary"
                data-testid="ai-task-action-btn-reexecute"
                data-action={action}
                onClick={() => {
                  setError(null)
                  setReexecOpen(true)
                }}
              >
                {aiAvailableActionLabel(action)}
              </Button>
            )
          }
          return (
            <Button
              key={action}
              type="button"
              size="sm"
              variant={action === 'cancel' ? 'danger' : 'secondary'}
              data-testid={`ai-task-action-btn-${action}`}
              data-action={action}
              onClick={() => {
                setError(null)
                if (
                  action === 'cancel' ||
                  action === 'resume' ||
                  action === 'system_failure_retry'
                ) {
                  setConfirm(action)
                }
              }}
            >
              {aiAvailableActionLabel(action)}
            </Button>
          )
        })}
      </div>

      {error && (
        <p
          className="text-xs text-danger-600 dark:text-danger-400"
          data-testid="ai-task-actions-error"
          role="alert"
        >
          {error}
        </p>
      )}

      {confirm && (
        <Modal
          open
          onClose={() => !busy && setConfirm(null)}
          title={<span id={titleId}>{confirmCopy[confirm].title}</span>}
          description={confirmCopy[confirm].description}
          size="sm"
          footer={
            <>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => setConfirm(null)}
              >
                返回
              </Button>
              <Button
                type="button"
                size="sm"
                variant={confirmCopy[confirm].danger ? 'danger' : 'primary'}
                loading={busy}
                data-testid={`ai-task-confirm-${confirm}`}
                onClick={() => void runControl(confirm)}
              >
                {confirmCopy[confirm].confirmLabel}
              </Button>
            </>
          }
        >
          <p className="text-sm text-ink-2 dark:text-dark-ink-secondary">
            任务版本 {task.task_version} · 状态 {task.status}
          </p>
        </Modal>
      )}

      <AIReexecutionDialog
        open={reexecOpen}
        taskId={task.task_id}
        taskVersion={task.task_version}
        pointCapPreview={
          pointPreview?.quoted_max ?? task.point_summary?.quoted_max ?? null
        }
        capability={task.capability}
        action={task.action}
        serviceTier={task.service_tier}
        onClose={() => setReexecOpen(false)}
        onAccepted={async (result) => {
          setReexecOpen(false)
          await invalidate()
          onAccepted?.(result, 'reexecute')
        }}
        onConflictRefresh={async () => {
          setReexecOpen(false)
          await invalidate()
          await onConflictRefresh?.()
        }}
      />
    </div>
  )
}
