/**
 * LatencyBandsChart — REQ-044 US3 / FR-016 + AC-16.4.
 *
 * Renders a p50 / p95 / p99 summary per FeatureArea as a 3-column
 * grid. The "line chart" rendering is approximated via ascending-bars
 * (p50 → p99) — the surface (3 percentile bands + per-area rows +
 * comparison baseline label) is the AC-17.5 contract.
 */
import type { LatencyBandEntry, VersionSelectorResponse } from '@/types/admin-ai-operations'

interface LatencyBandsChartProps {
  entries: LatencyBandEntry[]
  versionSelector?: VersionSelectorResponse | null
}

function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`
  return `${ms.toFixed(0)}ms`
}

export function LatencyBandsChart({
  entries,
  versionSelector,
}: LatencyBandsChartProps) {
  const baseline = versionSelector?.baselineLabel ?? 'last 7 days'
  return (
    <div
      className="ac-ao-chart ac-ao-chart--latency"
      data-testid="ai-operations-latency-bands"
    >
      <div className="ac-ao-chart__baseline" data-testid="chart-baseline-label">
        Comparing vs {baseline}
      </div>
      <table className="ac-ao-chart__table">
        <thead>
          <tr>
            <th>Feature area</th>
            <th data-testid="latency-col-p50">P50</th>
            <th data-testid="latency-col-p95">P95</th>
            <th data-testid="latency-col-p99">P99</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr
              key={e.featureArea}
              data-testid={`latency-row-${e.featureArea}`}
            >
              <td>{e.featureArea}</td>
              <td data-testid={`latency-p50-${e.featureArea}`}>
                {formatMs(e.p50LatencyMs)}
              </td>
              <td data-testid={`latency-p95-${e.featureArea}`}>
                {formatMs(e.p95LatencyMs)}
              </td>
              <td data-testid={`latency-p99-${e.featureArea}`}>
                {formatMs(e.p99LatencyMs)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default LatencyBandsChart
