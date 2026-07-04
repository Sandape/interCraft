/**
 * CostSummaryCard — REQ-044 US3 / FR-016 + AC-16.6 + EC-3.
 *
 * Total + per FeatureArea breakdown + freshness / stale flag.
 *
 * Edge Case EC-3: when ``stale=True`` the card renders the
 * "cost estimate outdated, last reconciled <date>" warning so the
 * PM knows the cost numbers are an estimate.
 */
import type { CostSummaryResponse } from '@/types/admin-ai-operations'

interface CostSummaryCardProps {
  summary: CostSummaryResponse
}

function formatUsd(usd: number): string {
  return `$${usd.toFixed(4)}`
}

export function CostSummaryCard({ summary }: CostSummaryCardProps) {
  return (
    <div
      className="ac-ao-card ac-ao-card--cost"
      data-testid="ai-operations-cost-summary"
    >
      <div className="ac-ao-card__header">
        <h3 className="ac-ao-card__title">Estimated cost (last 7 days)</h3>
        <span className="ac-ao-card__estimate-pill" data-testid="cost-estimate-pill">
          estimate · not for billing
        </span>
      </div>

      {summary.stale && (
        <div
          className="ac-ao-card__stale-warning"
          data-testid="cost-stale-warning"
          role="alert"
        >
          <strong>cost estimate outdated, last reconciled {summary.lastReconciledAt}</strong>
        </div>
      )}

      <div
        className="ac-ao-card__total"
        data-testid="cost-total"
      >
        {formatUsd(summary.totalCostUsd)}
      </div>

      <ul className="ac-ao-card__breakdown">
        {summary.byFeature.map((b) => (
          <li
            key={b.featureArea}
            className="ac-ao-card__breakdown-row"
            data-testid={`cost-row-${b.featureArea}`}
          >
            <span className="ac-ao-card__breakdown-label">{b.featureArea}</span>
            <span
              className="ac-ao-card__breakdown-value"
              data-testid={`cost-value-${b.featureArea}`}
            >
              {formatUsd(b.costUsd)}
            </span>
            <span
              className="ac-ao-card__breakdown-share"
              data-testid={`cost-share-${b.featureArea}`}
            >
              {(b.share * 100).toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>

      <div className="ac-ao-card__footer">
        <span data-testid="cost-last-reconciled">
          last reconciled at {summary.lastReconciledAt}
        </span>
      </div>
    </div>
  )
}

export default CostSummaryCard
