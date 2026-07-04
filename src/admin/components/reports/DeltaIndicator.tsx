/**
 * DeltaIndicator — REQ-044 US7 FR-030 AC-30.3 + EC-1.
 *
 * Renders one delta row between frozen and current values. When the
 * absolute delta exceeds the tolerance, the row is marked as a
 * "late-arriving data" warning (EC-1).
 */
import type { ComparisonDelta } from '@/types/admin-review-snapshots'

interface Props {
  delta: ComparisonDelta
  tolerancePct?: number
  'data-testid'?: string
}

export function DeltaIndicator({
  delta,
  tolerancePct = 0.5,
  'data-testid': testId,
}: Props) {
  const isLateArriving = Math.abs(delta.delta_pct) > tolerancePct
  const direction = delta.delta_pct > 0 ? 'up' : 'down'
  const className = `ac-delta-indicator${
    isLateArriving ? ' ac-delta-indicator--late-arriving' : ''
  }${
    delta.delta_pct > 0
      ? ' ac-delta-indicator--positive'
      : delta.delta_pct < 0
        ? ' ac-delta-indicator--negative'
        : ' ac-delta-indicator--zero'
  }`

  return (
    <div
      className={className}
      data-testid={testId ?? `delta-indicator-${delta.metric_id}`}
      data-metric-id={delta.metric_id}
      data-delta-pct={delta.delta_pct}
      data-late-arriving={isLateArriving ? 'true' : 'false'}
      role="status"
    >
      <span className="ac-delta-indicator__metric">{delta.metric_id}</span>
      <span className="ac-delta-indicator__value">
        Delta: {direction === 'up' ? '+' : ''}
        {delta.delta_pct.toFixed(1)}%
      </span>
      {isLateArriving ? (
        <span
          className="ac-delta-indicator__warn"
          data-testid="late-arriving"
          role="alert"
        >
          late-arriving data
        </span>
      ) : null}
      <span className="ac-delta-indicator__period">{delta.period}</span>
    </div>
  )
}

export default DeltaIndicator