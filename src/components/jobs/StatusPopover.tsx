/**
 * REQ-053 — StatusPopover (replaces the old `StatusTransition`).
 *
 * Owns three things for the new 7-state model:
 *  - T025: status labels come from `JOB_STATUS_LABELS` (not the old popover
 *    hardcoded list of `OA / HR / Offer`).
 *  - T026: shows a `<input type="datetime-local">` whenever the user picks
 *    a round-based target (test / interview_1 / interview_2 / interview_3).
 *    Field is required and client-side validated to be a future time.
 *  - T027: terminal states (failed / passed) collapse the popover trigger into
 *    a disabled button with a tooltip "已终结的岗位无法推进".
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Calendar, Loader2, MoreHorizontal, X } from 'lucide-react'
import { useJobTransitions } from '@/hooks/queries/useJobTransitions'
import { TerminalConfirmModal } from '@/components/jobs/TerminalConfirmModal'
import { Button } from '@/components/ui/Button'
import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/lib/utils'
import {
  JOB_STATUS_LABELS,
  TERMINAL_JOB_STATUSES,
  isInterviewStatus,
  isTerminalStatus,
} from '@/types/jobs'

const TERMINAL_SET = new Set<string>(TERMINAL_JOB_STATUSES)

interface StatusPopoverProps {
  jobId: string
  company: string
  position: string
  currentStatus: string
  onUpdate: (to: string, interviewTime?: string | null) => void
  onDelete: () => void
  isPending: boolean
  labels?: Record<string, string>
  error?: string | null
  onRetry?: (to: string, interviewTime?: string | null) => void
  lastAttemptedTo?: string | null
  lastAttemptedInterviewTime?: string | null
}

export function StatusPopover({
  jobId,
  company,
  position,
  currentStatus,
  onUpdate,
  onDelete,
  isPending,
  labels,
  error,
  onRetry,
  lastAttemptedTo,
  lastAttemptedInterviewTime,
}: StatusPopoverProps) {
  const { data } = useJobTransitions()
  const [open, setOpen] = useState(false)
  const [pendingTerminal, setPendingTerminal] = useState<string | null>(null)
  const [interviewTarget, setInterviewTarget] = useState<string | null>(null)
  const [interviewTime, setInterviewTime] = useState('')
  const [timeError, setTimeError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const labelFor = (k: string) => labels?.[k] ?? JOB_STATUS_LABELS[k] ?? k

  const allowedNext = useMemo(
    () =>
      data.transitions
        .filter((t) => t.from === currentStatus)
        .map((t) => t.to)
        .filter((to) => !(TERMINAL_SET.has(currentStatus) && to === currentStatus)),
    [data.transitions, currentStatus],
  )

  // T027 — terminal jobs cannot advance at all.
  const isTerminalNow = isTerminalStatus(currentStatus)

  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
        setInterviewTarget(null)
        setInterviewTime('')
        setTimeError(null)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  const resetForm = () => {
    setInterviewTarget(null)
    setInterviewTime('')
    setTimeError(null)
  }

  const handleSelect = (to: string) => {
    if (TERMINAL_SET.has(to)) {
      // confirm modal still owns the terminal flow (T027 spec).
      setOpen(false)
      setPendingTerminal(to)
      return
    }
    if (isInterviewStatus(to)) {
      // T026 — open the inline time picker for round-based targets.
      setInterviewTarget(to)
      setInterviewTime('')
      setTimeError(null)
      return
    }
    setOpen(false)
    onUpdate(to)
  }

  const submitInterview = () => {
    if (!interviewTarget) return
    if (!interviewTime) {
      setTimeError('面试时间不能为空')
      return
    }
    // <input type="datetime-local"> has no timezone — interpret as local
    // and serialize to ISO with offset so the backend can store TIMESTAMPTZ.
    const local = new Date(interviewTime)
    if (Number.isNaN(local.getTime())) {
      setTimeError('面试时间格式无效')
      return
    }
    const now = Date.now()
    if (local.getTime() <= now) {
      setTimeError('面试时间必须是将来时间')
      return
    }
    setOpen(false)
    onUpdate(interviewTarget, local.toISOString())
    resetForm()
  }

  // T027 — terminal jobs render a disabled icon with tooltip, no popover.
  if (isTerminalNow) {
    return (
      <Tooltip content="已终结的岗位无法推进">
        <span
          data-testid="status-popover-disabled"
          aria-disabled
          className="inline-flex p-1 rounded text-ink-muted cursor-not-allowed"
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </span>
      </Tooltip>
    )
  }

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        type="button"
        data-testid="status-popover-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="状态操作"
        className="p-1 rounded text-ink-3 hover:text-ink-1 hover:bg-surface-muted dark:hover:bg-dark-surface-muted"
        onClick={() => setOpen((v) => !v)}
      >
        <MoreHorizontal className="h-3.5 w-3.5" />
      </button>

      {open && (
        <div
          role="menu"
          data-testid="status-popover-menu"
          className="absolute right-0 mt-1 z-20 min-w-[240px] rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface shadow-notion-md py-1"
        >
          {allowedNext.length === 0 && (
            <div className="px-3 py-1.5 text-2xs text-ink-3">无下一步状态</div>
          )}
          {allowedNext.map((to) => (
            <button
              key={to}
              type="button"
              role="menuitem"
              data-testid={`status-menuitem-${to}`}
              onClick={() => handleSelect(to)}
              disabled={isPending}
              className={cn(
                'w-full text-left px-3 py-1.5 text-xs hover:bg-surface-muted dark:hover:bg-dark-surface-muted text-ink-1',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                interviewTarget === to && 'bg-surface-muted dark:bg-dark-surface-muted',
              )}
            >
              推进到 {labelFor(to)}
            </button>
          ))}

          {interviewTarget && (
            <InterviewTimePicker
              targetLabel={labelFor(interviewTarget)}
              value={interviewTime}
              error={timeError}
              disabled={isPending}
              onChange={setInterviewTime}
              onSubmit={submitInterview}
              onCancel={resetForm}
            />
          )}

          {error && onRetry && lastAttemptedTo && (
            <div className="px-3 py-1.5 border-t border-surface-border dark:border-dark-surface-border">
              <div
                className="text-2xs text-red-600 dark:text-red-400"
                data-testid={`row-error-${jobId}`}
              >
                {error}
              </div>
              <button
                type="button"
                data-testid="status-popover-retry"
                onClick={() => onRetry(lastAttemptedTo, lastAttemptedInterviewTime ?? null)}
                disabled={isPending}
                className="mt-1 text-2xs text-brand-600 hover:underline disabled:opacity-50"
              >
                重试
              </button>
            </div>
          )}
          <div className="border-t border-surface-border dark:border-dark-surface-border mt-1 pt-1">
            <button
              type="button"
              role="menuitem"
              data-testid={`status-menuitem-delete-${jobId}`}
              onClick={() => {
                setOpen(false)
                onDelete()
              }}
              className="w-full text-left px-3 py-1.5 text-xs text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10"
            >
              删除
            </button>
          </div>
        </div>
      )}

      <TerminalConfirmModal
        open={pendingTerminal !== null}
        to={pendingTerminal ?? ''}
        company={company}
        position={position}
        onConfirm={() => {
          if (pendingTerminal) onUpdate(pendingTerminal)
          setPendingTerminal(null)
        }}
        onCancel={() => setPendingTerminal(null)}
        isPending={isPending}
      />
    </div>
  )
}

interface InterviewTimePickerProps {
  targetLabel: string
  value: string
  error: string | null
  disabled: boolean
  onChange: (v: string) => void
  onSubmit: () => void
  onCancel: () => void
}

/**
 * T026 — Inline DateTimePicker embedded inside the popover. Uses the
 * platform-native `<input type="datetime-local">` (no external dep) so the
 * time picker renders in the user's locale and respects `min` for future-only
 * validation. We also re-validate `value > now` in submit (the min attribute
 * is best-effort across browsers).
 */
function InterviewTimePicker({
  targetLabel,
  value,
  error,
  disabled,
  onChange,
  onSubmit,
  onCancel,
}: InterviewTimePickerProps) {
  // `min` is the current local minute — keeps the browser from letting the
  // user pick a past time. ISO 8601 minus the trailing seconds / Z.
  const minLocal = useMemo(() => {
    const d = new Date()
    d.setSeconds(0, 0)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  }, [])

  return (
    <div
      data-testid="interview-time-picker"
      className="border-t border-surface-border dark:border-dark-surface-border px-3 py-2 space-y-2"
    >
      <div className="text-2xs text-ink-3 flex items-center gap-1.5">
        <Calendar className="h-3 w-3" />
        <span>
          推进到「{targetLabel}」需设置面试时间 <span className="text-red-500">*</span>
        </span>
      </div>
      <input
        type="datetime-local"
        data-testid="interview-time-input"
        value={value}
        min={minLocal}
        required
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-2 py-1.5 text-xs rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 border border-surface-border dark:border-dark-surface-border focus:outline-none focus:ring-2 focus:ring-brand-500/30"
      />
      {error && (
        <div
          data-testid="interview-time-error"
          className="text-2xs text-red-600 dark:text-red-400"
        >
          {error}
        </div>
      )}
      <div className="flex items-center justify-end gap-2">
        <Button
          size="sm"
          variant="ghost"
          data-testid="interview-time-cancel"
          onClick={onCancel}
          disabled={disabled}
          leftIcon={<X className="h-3 w-3" />}
        >
          取消
        </Button>
        <Button
          size="sm"
          variant="primary"
          data-testid="interview-time-submit"
          onClick={onSubmit}
          disabled={disabled}
          leftIcon={
            disabled ? <Loader2 className="h-3 w-3 animate-spin" /> : undefined
          }
        >
          确认推进
        </Button>
      </div>
    </div>
  )
}
