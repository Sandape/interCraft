/**
 * QuietState — REQ-044 US1 / FR-010.
 *
 * Rendered when ``high_severity_count == 0``. Shows:
 *
 *   - "quiet steady-state" headline
 *   - "No signals" when total == 0
 *   - "Last reviewed at: <timestamp>"
 *   - "Open reviews: <count>"
 *   - freshness_at for 4 sections (product / ai quality / ai cost /
 *     system health)
 *
 * The component must NOT manufacture alerts (FR-010 / EC-1).
 */
import type { DecisionSignalListResponse } from '@/types/admin-decision-signals'

interface QuietStateProps {
  response: DecisionSignalListResponse
}

function fmt(ts: string): string {
  if (!ts || ts === 'unknown') return 'unknown (stale)'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  return d.toLocaleString()
}

export function QuietState({ response }: QuietStateProps) {
  return (
    <div className="ds-quiet" data-testid="quiet-steady-state">
      <div className="ds-quiet__headline" data-testid="quiet-headline">
        <span className="ds-quiet__pulse" aria-hidden="true" />
        quiet steady-state
      </div>
      <p className="ds-quiet__lede" data-testid="quiet-lede">
        当前没有 high-severity signal · 不制造伪告警
      </p>
      {response.total === 0 ? (
        <p className="ds-quiet__no-signals" data-testid="quiet-no-signals">
          No signals · 数据有效为零
        </p>
      ) : (
        <p
          className="ds-quiet__low-severity-count"
          data-testid="quiet-low-severity-count"
        >
          {response.total} 条非高严重度 signal · 见下方列表
        </p>
      )}
      <dl className="ds-quiet__meta">
        <dt>Last reviewed at:</dt>
        <dd data-testid="last-reviewed-at">{fmt(response.lastReviewedAt)}</dd>
        <dt>Open reviews:</dt>
        <dd data-testid="open-reviews-count">{response.openReviews}</dd>
        <dt>Freshness (overall):</dt>
        <dd data-testid="freshness-overall">{fmt(response.freshnessAt)}</dd>
        <dt>Freshness (product / ai-quality / ai-cost / system-health):</dt>
        <dd data-testid="freshness-sections">{fmt(response.freshnessAt)}</dd>
      </dl>
    </div>
  )
}

export default QuietState