/**
 * VolumeByFeatureChart — REQ-044 US3 / FR-016 + AC-16.2.
 *
 * Renders a horizontal bar chart per FeatureArea (call_count +
 * success_count + failure_count). Comparison baseline label surfaces
 * at the top (AC-17.5).
 */
import type { VersionSelectorResponse, VolumeByFeatureRow } from '@/types/admin-ai-operations'

interface VolumeByFeatureChartProps {
  rows: VolumeByFeatureRow[]
  versionSelector?: VersionSelectorResponse | null
}

export function VolumeByFeatureChart({
  rows,
  versionSelector,
}: VolumeByFeatureChartProps) {
  const baseline = versionSelector?.baselineLabel ?? 'last 7 days'
  const max = Math.max(...rows.map((r) => r.callCount), 1)

  return (
    <div
      className="ac-ao-chart ac-ao-chart--volume"
      data-testid="ai-operations-volume-chart"
    >
      <div className="ac-ao-chart__baseline" data-testid="chart-baseline-label">
        Comparing vs {baseline}
      </div>
      <ul className="ac-ao-chart__bars">
        {rows.map((r) => {
          const w = Math.max(2, (r.callCount / max) * 100)
          return (
            <li
              key={r.featureArea}
              className="ac-ao-chart__bar-row"
              data-testid={`volume-row-${r.featureArea}`}
            >
              <div className="ac-ao-chart__bar-label">{r.featureArea}</div>
              <div
                className="ac-ao-chart__bar"
                style={{ width: `${w}%` }}
                aria-hidden
              />
              <div
                className="ac-ao-chart__bar-count"
                data-testid={`volume-count-${r.featureArea}`}
              >
                {r.callCount.toLocaleString()} (
                <span data-testid={`volume-success-${r.featureArea}`}>
                  {r.successCount.toLocaleString()} ok
                </span>
                {' · '}
                <span data-testid={`volume-failure-${r.featureArea}`}>
                  {r.failureCount.toLocaleString()} fail
                </span>
                )
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default VolumeByFeatureChart
