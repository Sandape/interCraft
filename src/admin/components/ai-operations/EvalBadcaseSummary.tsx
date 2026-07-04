/**
 * EvalBadcaseSummary — REQ-044 US3 / FR-020 + AC-20.1/20.2/20.3.
 *
 * Workspace eval + badcase summary card. Shows:
 *
 *   - total_eval_runs + pass_rate + open_runs (AC-20.1)
 *   - 5 most-recent badcases (AC-20.2) — id + feature_area +
 *     eval_verdict + status + opened_at
 *   - "View in Logs" button → logs-and-traces workspace (US5
 *     placeholder route, AC-20.3)
 *
 * The card surfaces the eval + badcase status so PM does not have
 * to open developer-only logs.
 */
import type { EvalBadcaseSummary } from '@/types/admin-ai-operations'

interface EvalBadcaseSummaryProps {
  summary: EvalBadcaseSummary
  onViewInLogs: () => void
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

export function EvalBadcaseSummaryCard({
  summary,
  onViewInLogs,
}: EvalBadcaseSummaryProps) {
  return (
    <div
      className="ac-ao-card ac-ao-card--eval-badcase"
      data-testid="ai-operations-eval-badcase-summary"
    >
      <h3 className="ac-ao-card__title">Eval · Badcase summary</h3>

      <div className="ac-ao-card__metrics">
        <div
          className="ac-ao-card__metric"
          data-testid="eval-total-runs"
        >
          <div className="ac-ao-card__metric-label">Total eval runs</div>
          <div className="ac-ao-card__metric-value">
            {summary.evalRunSummary.totalRuns.toLocaleString()}
          </div>
        </div>
        <div
          className="ac-ao-card__metric"
          data-testid="eval-pass-rate"
        >
          <div className="ac-ao-card__metric-label">Pass rate</div>
          <div className="ac-ao-card__metric-value">
            {formatPct(summary.evalRunSummary.passRate)}
          </div>
        </div>
        <div
          className="ac-ao-card__metric"
          data-testid="open-badcases-count"
        >
          <div className="ac-ao-card__metric-label">Open badcases</div>
          <div className="ac-ao-card__metric-value">
            {summary.openBadcasesCount}
          </div>
        </div>
      </div>

      <h4
        className="ac-ao-card__sub-title"
        data-testid="recent-badcases-title"
      >
        Recent Badcases (latest {summary.recentBadcases.length})
      </h4>
      <ul className="ac-ao-card__list">
        {summary.recentBadcases.slice(0, 5).map((b) => (
          <li
            key={b.badcaseId}
            className="ac-ao-card__list-row"
            data-testid={`recent-badcase-${b.badcaseId}`}
          >
            <span
              className="ac-ao-card__list-id"
              data-testid={`recent-badcase-id-${b.badcaseId}`}
            >
              {b.badcaseId}
            </span>
            <span data-testid={`recent-badcase-area-${b.badcaseId}`}>
              {b.featureArea}
            </span>
            <span
              className="ac-ao-card__list-verdict"
              data-testid={`recent-badcase-verdict-${b.badcaseId}`}
            >
              {b.evalVerdict}
            </span>
            <span
              className="ac-ao-card__list-status"
              data-testid={`recent-badcase-status-${b.badcaseId}`}
            >
              {b.status}
            </span>
          </li>
        ))}
      </ul>

      <button
        type="button"
        onClick={onViewInLogs}
        className="ac-ao-card__action"
        data-testid="view-in-logs-button"
      >
        View in Logs (US5 placeholder)
      </button>
    </div>
  )
}

export default EvalBadcaseSummaryCard
