/**
 * TokenUsageChart — REQ-044 US3 / FR-016 + AC-16.5.
 *
 * Stacked bar per FeatureArea: prompt_tokens (input) +
 * completion_tokens (output) + total. Comparison baseline label
 * surfaces at the top (AC-17.5).
 */
import type { TokenUsageRow, VersionSelectorResponse } from '@/types/admin-ai-operations'

interface TokenUsageChartProps {
  rows: TokenUsageRow[]
  versionSelector?: VersionSelectorResponse | null
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return n.toString()
}

export function TokenUsageChart({
  rows,
  versionSelector,
}: TokenUsageChartProps) {
  const baseline = versionSelector?.baselineLabel ?? 'last 7 days'
  const max = Math.max(...rows.map((r) => r.totalTokens), 1)

  return (
    <div
      className="ac-ao-chart ac-ao-chart--token"
      data-testid="ai-operations-token-usage"
    >
      <div className="ac-ao-chart__baseline" data-testid="chart-baseline-label">
        Comparing vs {baseline}
      </div>
      <ul className="ac-ao-chart__stacked">
        {rows.map((r) => {
          const inputPct = (r.promptTokens / max) * 100
          const outputPct = (r.completionTokens / max) * 100
          return (
            <li
              key={r.featureArea}
              className="ac-ao-chart__stacked-row"
              data-testid={`token-row-${r.featureArea}`}
            >
              <div className="ac-ao-chart__bar-label">{r.featureArea}</div>
              <div className="ac-ao-chart__stacked-bar" style={{ width: `${inputPct + outputPct}%` }}>
                <span
                  className="ac-ao-chart__stacked-bar-input"
                  style={{ width: `${(inputPct / (inputPct + outputPct || 1)) * 100}%` }}
                  data-testid={`token-input-${r.featureArea}`}
                />
                <span
                  className="ac-ao-chart__stacked-bar-output"
                  style={{ width: `${(outputPct / (inputPct + outputPct || 1)) * 100}%` }}
                  data-testid={`token-output-${r.featureArea}`}
                />
              </div>
              <div
                className="ac-ao-chart__bar-count"
                data-testid={`token-total-${r.featureArea}`}
              >
                {formatTokens(r.totalTokens)} (
                <span data-testid={`token-input-amount-${r.featureArea}`}>
                  {formatTokens(r.promptTokens)} in
                </span>
                {' · '}
                <span data-testid={`token-output-amount-${r.featureArea}`}>
                  {formatTokens(r.completionTokens)} out
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

export default TokenUsageChart
