/**
 * TrendArrow — REQ-044 US4 / FR-021.
 *
 * Visual differentiation for the 3 incident trend directions:
 *
 *   - rising:    ↑ red
 *   - stable:    → gray
 *   - declining: ↓ green
 */
import type { IncidentTrend } from '@/types/admin-incidents'

interface TrendArrowProps {
  trend: IncidentTrend
}

const TREND_GLYPH: Record<IncidentTrend, string> = {
  rising: '↑',
  stable: '→',
  declining: '↓',
}

const TREND_LABEL: Record<IncidentTrend, string> = {
  rising: 'Rising — frequency or impact increasing',
  stable: 'Stable — unchanged',
  declining: 'Declining — improving',
}

export function TrendArrow({ trend }: TrendArrowProps) {
  return (
    <span
      className={`ic-trend ic-trend--${trend}`}
      data-testid={`trend-${trend}`}
      data-trend={trend}
      title={TREND_LABEL[trend]}
      aria-label={TREND_LABEL[trend]}
    >
      <span className="ic-trend__glyph" aria-hidden="true">
        {TREND_GLYPH[trend]}
      </span>
    </span>
  )
}

export default TrendArrow
