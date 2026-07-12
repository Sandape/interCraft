/**
 * REQ-061 (US1) — User-safe failure explanation (no provider/internal details).
 *
 * Renders only fields from `FailurePresentation` — never invents next steps
 * or point effects from status strings.
 */
import { cn } from '@/lib/utils'
import type { FailurePresentation } from '@/types/ai-runtime'

export interface AIFailurePanelProps {
  failure: FailurePresentation | null | undefined
  className?: string
}

export function AIFailurePanel({ failure, className }: AIFailurePanelProps) {
  if (!failure) return null

  return (
    <section
      className={cn(
        'space-y-3 rounded border border-surface-border dark:border-dark-surface-border',
        'bg-danger-50 dark:bg-danger-500/10 p-4',
        className,
      )}
      data-testid="ai-failure-panel"
      data-failure-category={failure.category}
      aria-label="任务失败说明"
    >
      <header className="space-y-1">
        <p className="text-xs font-medium text-danger-600 dark:text-danger-400">
          {failure.category}
        </p>
        <h3 className="text-sm font-semibold text-ink-1 dark:text-dark-ink-primary">
          {failure.what_happened}
        </h3>
      </header>

      <dl className="space-y-2 text-sm text-ink-2 dark:text-dark-ink-secondary">
        <div>
          <dt className="text-xs text-ink-3 dark:text-dark-ink-tertiary">已保存</dt>
          <dd data-testid="ai-failure-saved">{failure.what_was_saved}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-3 dark:text-dark-ink-tertiary">点数影响</dt>
          <dd data-testid="ai-failure-points">{failure.point_effect}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-3 dark:text-dark-ink-tertiary">系统下一步</dt>
          <dd data-testid="ai-failure-system-next">{failure.system_next_step}</dd>
        </div>
      </dl>

      {failure.user_next_steps.length > 0 && (
        <div>
          <p className="mb-1 text-xs text-ink-3 dark:text-dark-ink-tertiary">你可以</p>
          <ul
            className="list-disc space-y-1 pl-4 text-sm text-ink-2 dark:text-dark-ink-secondary"
            data-testid="ai-failure-user-steps"
          >
            {failure.user_next_steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </div>
      )}

      {failure.support_ref && (
        <p
          className="text-xs text-ink-3 dark:text-dark-ink-tertiary"
          data-testid="ai-failure-support-ref"
        >
          支持编号 {failure.support_ref}
        </p>
      )}
    </section>
  )
}
