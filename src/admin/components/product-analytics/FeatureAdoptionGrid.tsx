/**
 * FeatureAdoptionGrid — REQ-044 US2 / FR-014.
 *
 * Renders the 5-metric grid per feature:
 * discovery_users / first_use_users / repeat_users / frequency_avg /
 * downstream_success_rate.
 *
 * Each metric is rendered as a SEPARATE cell — the 5 metrics are
 * NEVER collapsed into a single adoption score (AC-14.3). The grid
 * also surfaces comparison_period delta and the "Insufficient data"
 * badge for sample_size below the FR-028 threshold (EC-3).
 */
import type {
  FeatureAdoptionMetric,
  FeatureAdoptionRow,
} from '@/types/admin-product-analytics'

interface FeatureAdoptionGridProps {
  rows: FeatureAdoptionRow[]
}

const METRIC_LABELS: Record<FeatureAdoptionMetric['metricName'], string> = {
  discovery_users: 'Discovery',
  first_use_users: 'First use',
  repeat_users: 'Repeat use',
  frequency_avg: 'Frequency (avg)',
  downstream_success_rate: 'Downstream success',
}

function formatMetric(metric: FeatureAdoptionMetric): string {
  if (metric.unit === 'count') {
    return Math.round(metric.currentValue).toLocaleString()
  }
  if (metric.unit === 'rate') {
    return `${(metric.currentValue * 100).toFixed(1)}%`
  }
  if (metric.unit === 'per_user_per_week') {
    return metric.currentValue.toFixed(2)
  }
  return metric.currentValue.toString()
}

function formatDelta(delta: number): string {
  const sign = delta > 0 ? '+' : delta < 0 ? '' : ''
  return `${sign}${(delta * 100).toFixed(1)}%`
}

export function FeatureAdoptionGrid({ rows }: FeatureAdoptionGridProps) {
  if (!rows.length) {
    return (
      <div
        className="ac-pa-adoption ac-pa-adoption--empty"
        data-testid="feature-adoption-empty"
      >
        暂无 feature adoption 数据
      </div>
    )
  }

  return (
    <div className="ac-pa-adoption" data-testid="feature-adoption-grid">
      {rows.map((row) => {
        const anyInsufficient = row.metrics.some((m) => m.insufficientData)
        return (
          <div
            key={row.featureId}
            className="ac-pa-adoption__feature"
            data-testid={`feature-adoption-row-${row.featureId}`}
          >
            <div className="ac-pa-adoption__header">
              <span
                className="ac-pa-adoption__feature-name"
                data-testid={`feature-adoption-name-${row.featureId}`}
              >
                {row.featureName}
              </span>
              <span
                className="ac-pa-adoption__cohort"
                data-testid={`feature-adoption-cohort-${row.featureId}`}
              >
                cohort {row.cohortId ?? '全量'} · pop{' '}
                {row.cohortPopulation.toLocaleString()} · last computed{' '}
                {row.lastComputedAt}
              </span>
            </div>

            {anyInsufficient && (
              <div
                className="ac-pa-adoption__insufficient"
                data-testid="feature-adoption-insufficient-data"
                role="status"
              >
                Insufficient data — sample size below threshold (FR-028 / EC-3)
              </div>
            )}

            <div className="ac-pa-adoption__metrics">
              {row.metrics.map((metric) => (
                <div
                  key={metric.metricName}
                  className="ac-pa-adoption__metric"
                  data-testid={`feature-adoption-metric-${row.featureId}-${metric.metricName}`}
                >
                  <span className="ac-pa-adoption__metric-label">
                    {METRIC_LABELS[metric.metricName]}
                  </span>
                  <span className="ac-pa-adoption__metric-value">
                    {formatMetric(metric)}
                  </span>
                  <span className="ac-pa-adoption__metric-delta">
                    vs prev {formatDelta(metric.comparisonDelta)}
                  </span>
                  <span className="ac-pa-adoption__metric-sample">
                    n = {metric.sampleSize}
                  </span>
                  {metric.insufficientData && (
                    <span
                      className="ac-pa-adoption__metric-insufficient"
                      data-testid={`feature-adoption-insufficient-${row.featureId}-${metric.metricName}`}
                    >
                      Insufficient data
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default FeatureAdoptionGrid