/**
 * REQ-061 (US2) — Re-execution dialog (new charge lineage, not evidence replay).
 *
 * Lets the user choose input/behavior versions, preview the point cap via a
 * fresh quote, and submit with expected_task_version. 409 conflicts trigger
 * refresh rather than silent retry.
 */
import { useCallback, useEffect, useState } from 'react'
import {
  createAITaskQuote,
  reexecuteAITask,
} from '@/api/ai-runtime'
import { ApiError } from '@/api/errors'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import type {
  PointQuote,
  ReexecutionRequest,
  ServiceTier,
  TaskAccepted,
} from '@/types/ai-runtime'

type InputMode = ReexecutionRequest['input_mode']
type BehaviorMode = ReexecutionRequest['behavior_mode']

function newIdempotencyKey(prefix: string): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `${prefix}-${crypto.randomUUID()}`
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export interface AIReexecutionDialogProps {
  open: boolean
  taskId: string
  taskVersion: number
  /** Displayed while quoting / as fallback cap. */
  pointCapPreview?: number | null
  capability?: string
  action?: string
  serviceTier?: ServiceTier
  onClose: () => void
  onAccepted: (result: TaskAccepted) => void | Promise<void>
  onConflictRefresh?: () => void | Promise<void>
}

export function AIReexecutionDialog({
  open,
  taskId,
  taskVersion,
  pointCapPreview = null,
  capability = 'resume_derive',
  action = 'derive',
  serviceTier = 'standard',
  onClose,
  onAccepted,
  onConflictRefresh,
}: AIReexecutionDialogProps) {
  const [inputMode, setInputMode] = useState<InputMode>('original_snapshot')
  const [behaviorMode, setBehaviorMode] =
    useState<BehaviorMode>('current_stable')
  const [quote, setQuote] = useState<PointQuote | null>(null)
  const [quoting, setQuoting] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) {
      setQuote(null)
      setError(null)
      setInputMode('original_snapshot')
      setBehaviorMode('current_stable')
      return
    }
    let cancelled = false
    const run = async () => {
      setQuoting(true)
      setError(null)
      try {
        const next = await createAITaskQuote(
          {
            capability,
            action,
            service_tier: serviceTier,
            input_snapshot_ref: `reexec:${taskId}:${Date.now()}`,
            allow_degrade: false,
          },
          newIdempotencyKey('reexec-quote'),
        )
        if (!cancelled) setQuote(next)
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? err.message
              : err instanceof Error
                ? err.message
                : '报价失败',
          )
        }
      } finally {
        if (!cancelled) setQuoting(false)
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [open, capability, action, serviceTier, taskId])

  const cap =
    quote?.max_points ??
    (typeof pointCapPreview === 'number' ? pointCapPreview : null)

  const submit = useCallback(async () => {
    if (!quote) {
      setError('请等待点数报价完成')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const result = await reexecuteAITask(
        taskId,
        {
          expected_task_version: taskVersion,
          input_mode: inputMode,
          behavior_mode: behaviorMode,
          quote_id: quote.quote_id,
        },
        newIdempotencyKey('reexec'),
      )
      await onAccepted(result)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(
          err.code === 'VERSION_CONFLICT'
            ? '任务版本冲突，已请求刷新'
            : err.message,
        )
        await onConflictRefresh?.()
        return
      }
      setError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : '重新执行失败',
      )
    } finally {
      setSubmitting(false)
    }
  }, [
    behaviorMode,
    inputMode,
    onAccepted,
    onConflictRefresh,
    quote,
    taskId,
    taskVersion,
  ])

  return (
    <Modal
      open={open}
      onClose={() => !submitting && onClose()}
      title="重新执行任务"
      description="将创建新的执行谱系与点数预留；这不是只读证据回放。"
      size="md"
      footer={
        <>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            disabled={submitting}
            onClick={onClose}
          >
            取消
          </Button>
          <Button
            type="button"
            size="sm"
            variant="primary"
            loading={submitting || quoting}
            disabled={!quote || quoting}
            data-testid="ai-reexec-submit"
            onClick={() => void submit()}
          >
            确认重新执行
          </Button>
        </>
      }
    >
      <div className="space-y-4" data-testid="ai-reexecution-dialog">
        <fieldset className="space-y-2">
          <legend className="text-xs font-medium text-ink-3 dark:text-dark-ink-tertiary">
            输入版本
          </legend>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="input_mode"
              value="original_snapshot"
              checked={inputMode === 'original_snapshot'}
              onChange={() => setInputMode('original_snapshot')}
              data-testid="ai-reexec-input-original"
            />
            原始输入快照
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="input_mode"
              value="latest_snapshot"
              checked={inputMode === 'latest_snapshot'}
              onChange={() => setInputMode('latest_snapshot')}
              data-testid="ai-reexec-input-latest"
            />
            最新输入快照
          </label>
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="text-xs font-medium text-ink-3 dark:text-dark-ink-tertiary">
            行为版本
          </legend>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="behavior_mode"
              value="original_locked"
              checked={behaviorMode === 'original_locked'}
              onChange={() => setBehaviorMode('original_locked')}
              data-testid="ai-reexec-behavior-original"
            />
            锁定原始策略
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="behavior_mode"
              value="current_stable"
              checked={behaviorMode === 'current_stable'}
              onChange={() => setBehaviorMode('current_stable')}
              data-testid="ai-reexec-behavior-current"
            />
            当前稳定策略
          </label>
        </fieldset>

        <div
          className="rounded border border-surface-border dark:border-dark-surface-border p-3 text-sm"
          data-testid="ai-reexec-point-preview"
        >
          <p className="text-xs text-ink-3 dark:text-dark-ink-tertiary mb-1">
            点数上限预览
          </p>
          {quoting && <p>正在获取报价…</p>}
          {!quoting && cap !== null && (
            <p>
              上限 <strong data-testid="ai-reexec-point-cap">{cap}</strong> 点
              {quote && (
                <span className="ml-2 text-xs text-ink-3">
                  余额 {quote.balance_before} → 预留后约{' '}
                  {quote.projected_available_after_reservation}
                </span>
              )}
            </p>
          )}
          {!quoting && cap === null && <p>暂无报价</p>}
        </div>

        <p className="text-xs text-ink-3 dark:text-dark-ink-tertiary">
          任务版本 {taskVersion}
        </p>

        {error && (
          <p
            className="text-xs text-danger-600 dark:text-danger-400"
            role="alert"
            data-testid="ai-reexec-error"
          >
            {error}
          </p>
        )}
      </div>
    </Modal>
  )
}
