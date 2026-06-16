import { useEffect, useRef, useState } from 'react'
import { MoreHorizontal } from 'lucide-react'
import { useJobTransitions } from '@/hooks/queries/useJobTransitions'
import { TerminalConfirmModal } from '@/components/jobs/TerminalConfirmModal'
import { cn } from '@/lib/utils'

const TERMINAL_STATUSES = new Set(['rejected', 'withdrawn'])

interface StatusPopoverProps {
  jobId: string
  company: string
  position: string
  currentStatus: string
  onUpdate: (to: string) => void
  onDelete: () => void
  isPending: boolean
  labels?: Record<string, string>
  error?: string | null
  onRetry?: (to: string) => void
  lastAttemptedTo?: string | null
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
}: StatusPopoverProps) {
  const { data } = useJobTransitions()
  const [open, setOpen] = useState(false)
  const [pendingTerminal, setPendingTerminal] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const labelFor = (k: string) => labels?.[k] ?? k

  const allowedNext = data.transitions
    .filter((t) => t.from === currentStatus)
    .map((t) => t.to)

  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  const handleSelect = (to: string) => {
    setOpen(false)
    if (TERMINAL_STATUSES.has(to)) {
      setPendingTerminal(to)
    } else {
      onUpdate(to)
    }
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
          className="absolute right-0 mt-1 z-20 min-w-[180px] rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface shadow-notion-md py-1"
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
              )}
            >
              推进到 {labelFor(to)}
            </button>
          ))}
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
                onClick={() => onRetry(lastAttemptedTo)}
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
