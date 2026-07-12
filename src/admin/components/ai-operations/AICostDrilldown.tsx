/**
 * REQ-061 T122 — attempt/cost/rate/adjustment drilldown drawer.
 */
import type { TaskCostDrilldown } from '@/admin/api/ai-operations'

export interface AICostDrilldownProps {
  open: boolean
  onClose: () => void
  drilldown: TaskCostDrilldown | null
  isLoading?: boolean
  errorMessage?: string | null
}

export function AICostDrilldown({
  open,
  onClose,
  drilldown,
  isLoading,
  errorMessage,
}: AICostDrilldownProps) {
  if (!open) return null

  return (
    <div
      className="fixed inset-y-0 right-0 z-40 w-full max-w-md border-l border-surface-border bg-surface p-4 shadow-lg"
      data-testid="ai-cost-drilldown"
      role="dialog"
      aria-label="成本下钻"
    >
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Attempt / Cost</h2>
        <button type="button" onClick={onClose} data-testid="ai-cost-drilldown-close">
          关闭
        </button>
      </div>

      {isLoading && (
        <p className="text-xs text-ink-3" data-testid="drilldown-loading">
          加载中…
        </p>
      )}
      {errorMessage && (
        <p className="text-xs text-danger" role="alert" data-testid="drilldown-error">
          {errorMessage}
        </p>
      )}

      {drilldown && (
        <>
          <div className="mb-2 text-sm" data-testid="drilldown-task-id">
            task={drilldown.task_id}
          </div>
          <div className="mb-3 text-xs text-ink-3" data-testid="ai-cost-data-quality">
            status={drilldown.cost_status} · settled={drilldown.point_settled} · cost=
            {drilldown.current_cost_rmb.amount} {drilldown.current_cost_rmb.currency} · unknown{' '}
            {drilldown.data_quality.unknown_count}
          </div>

          <ul className="space-y-2 overflow-y-auto text-sm" style={{ maxHeight: '80vh' }}>
            {drilldown.attempts.map((row, idx) => (
              <li
                key={row.attempt_id}
                className="rounded border border-line-2 px-3 py-2"
                data-testid={`drilldown-attempt-${idx}`}
              >
                <div className="font-medium">{row.attempt_id}</div>
                <div className="text-xs text-ink-3">
                  {row.cost_status}
                  {row.cost ? ` · ${row.cost.amount} ${row.cost.currency}` : ''}
                </div>
                <div className="text-xs" data-testid={`drilldown-rate-${idx}`}>
                  rate={row.cost_rate_version ?? 'unknown'}
                </div>
                <div className="text-xs" data-testid={`drilldown-adjustment-${idx}`}>
                  adjustment={row.adjustment ?? '0'}
                </div>
              </li>
            ))}
            {drilldown.attempts.length === 0 && (
              <li className="text-ink-3">无 attempt 成本行</li>
            )}
          </ul>
        </>
      )}
    </div>
  )
}

export default AICostDrilldown
