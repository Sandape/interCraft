/**
 * MetricTooltip — REQ-044 FR-027 / AC-27.1.
 *
 * Renders the full 10-field metric definition tooltip. Per AC-27.4
 * missing fields render as the literal ``"(not provided)"`` so the
 * frontend never silently drops a column. Used by US1 decision signal
 * / US2 funnel / US3 KPI tooltip pointers (AC-27.3).
 */
import { QualityFlagsBadge } from '@/admin/components/governance/QualityFlagsBadge'
import {
  NOT_PROVIDED,
  type MetricDefinition10Field,
} from '@/types/admin-review-snapshots'

interface Props {
  metric: MetricDefinition10Field
  /** Toggle: 'card' (default) renders a static panel, 'popover' a small bubble */
  variant?: 'card' | 'popover'
  'data-testid'?: string
}

const ROWS: Array<{ key: keyof MetricDefinition10Field; label: string }> = [
  { key: 'definition', label: 'Definition' },
  { key: 'owner', label: 'Owner' },
  { key: 'source', label: 'Source' },
  { key: 'numerator', label: 'Numerator' },
  { key: 'denominator', label: 'Denominator' },
  { key: 'unit', label: 'Unit' },
  { key: 'period', label: 'Period' },
  { key: 'freshness', label: 'Freshness' },
  { key: 'completeness', label: 'Completeness' },
]

export function MetricTooltip({
  metric,
  variant = 'card',
  'data-testid': testId,
}: Props) {
  return (
    <div
      className={`ac-metric-tooltip ac-metric-tooltip--${variant}`}
      data-testid={testId ?? 'metric-tooltip'}
      data-metric-id={metric.metric_id}
      role="tooltip"
    >
      <div className="ac-metric-tooltip__title">
        {metric.name}{' '}
        <span className="ac-metric-tooltip__id">({metric.metric_id})</span>
      </div>
      <dl className="ac-metric-tooltip__list">
        {ROWS.map((r) => {
          const value = metric[r.key]
          const isMissing = value === NOT_PROVIDED || value == null || value === ''
          return (
            <div key={r.key} className="ac-metric-tooltip__row">
              <dt className="ac-metric-tooltip__label">{r.label}</dt>
              <dd
                className={`ac-metric-tooltip__value${
                  isMissing ? ' ac-metric-tooltip__value--missing' : ''
                }`}
                data-metric-field={r.key}
                data-missing={isMissing ? 'true' : 'false'}
              >
                {isMissing ? NOT_PROVIDED : value}
              </dd>
            </div>
          )
        })}
        <div className="ac-metric-tooltip__row">
          <dt className="ac-metric-tooltip__label">Quality Flags</dt>
          <dd
            className="ac-metric-tooltip__value"
            data-metric-field="quality_flags"
          >
            <QualityFlagsBadge status={metric.quality_flags} size="sm" />
          </dd>
        </div>
      </dl>
    </div>
  )
}

export default MetricTooltip