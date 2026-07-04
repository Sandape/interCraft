/**
 * FailureCategoriesPie — REQ-044 US3 / FR-016 + AC-16.3.
 *
 * Renders a textual pie-summary for the 5 FR-016 failure categories.
 * (Phase 1 ships a deterministic SVG-free representation; Phase 2
 * batch 3 can swap in Recharts/Pie. The surface stays the same.)
 *
 * Each row carries category + count + share + comparison baseline.
 */
import type { FailureCategoryBreakdown, VersionSelectorResponse } from '@/types/admin-ai-operations'

interface FailureCategoriesPieProps {
  rows: FailureCategoryBreakdown[]
  versionSelector?: VersionSelectorResponse | null
}

const CATEGORY_COLORS: Record<string, string> = {
  timeout: '#f59e0b',
  token_limit: '#7c3aed',
  parse_error: '#0891b2',
  eval_failed: '#dc2626',
  api_5xx: '#be123c',
}

export function FailureCategoriesPie({
  rows,
  versionSelector,
}: FailureCategoriesPieProps) {
  const baseline = versionSelector?.baselineLabel ?? 'last 7 days'
  return (
    <div
      className="ac-ao-chart ac-ao-chart--failure"
      data-testid="ai-operations-failure-categories"
    >
      <div className="ac-ao-chart__baseline" data-testid="chart-baseline-label">
        Comparing vs {baseline}
      </div>
      <ul className="ac-ao-chart__legend">
        {rows.map((r) => {
          const color = CATEGORY_COLORS[r.category] ?? '#94a3b8'
          return (
            <li
              key={r.category}
              className="ac-ao-chart__legend-row"
              data-testid={`failure-row-${r.category}`}
            >
              <span
                className="ac-ao-chart__legend-swatch"
                style={{ background: color }}
              />
              <span className="ac-ao-chart__legend-label">{r.category}</span>
              <span
                className="ac-ao-chart__legend-count"
                data-testid={`failure-count-${r.category}`}
              >
                {r.count.toLocaleString()}
              </span>
              <span
                className="ac-ao-chart__legend-share"
                data-testid={`failure-share-${r.category}`}
              >
                {(r.share * 100).toFixed(1)}%
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default FailureCategoriesPie
