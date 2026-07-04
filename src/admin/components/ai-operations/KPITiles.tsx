/**
 * KPITiles — REQ-044 US3 / FR-016 + AC-16.1.
 *
 * 4 workspace-header KPI tiles: total_volume / success_rate /
 * p95_latency / total_cost. Each tile carries the freshness_at
 * badge from the backend payload (FR-028 stale marker).
 *
 * Edge Case EC-1: zero AI tasks → render the "0 AI tasks" banner
 * above the tiles instead of silent empty fallback.
 */
import type { KPIBundle } from '@/types/admin-ai-operations'

interface KPITilesProps {
  kpis: KPIBundle
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`
  return `${ms.toFixed(0)}ms`
}

function formatUsd(usd: number): string {
  return `$${usd.toFixed(4)}`
}

function FreshnessBadge({ freshnessAt }: { freshnessAt: string }) {
  const stale = freshnessAt === 'unknown'
  return (
    <span
      className={
        stale
          ? 'ac-ao-kpi__tile__freshness ac-ao-kpi__tile__freshness--stale'
          : 'ac-ao-kpi__tile__freshness'
      }
      data-testid={stale ? 'kpi-freshness-stale' : 'kpi-freshness-fresh'}
      role={stale ? 'status' : undefined}
    >
      {stale ? '⚠ freshness unknown' : `freshness ${freshnessAt}`}
    </span>
  )
}

export function KPITiles({ kpis }: KPITilesProps) {
  const isZero = kpis.totalVolume === 0
  return (
    <div
      className="ac-ao-kpi ac-ao-kpi__tiles"
      data-testid="ai-operations-kpi-tiles"
    >
      {isZero && (
        <div
          className="ac-ao-kpi__zero"
          data-testid="ai-operations-zero-banner"
          role="status"
        >
          <strong>0 AI tasks</strong> — valid zero per FR-028 (no silent fallback)
        </div>
      )}

      <div className="ac-ao-kpi__tile" data-testid="kpi-tile-total-volume">
        <div className="ac-ao-kpi__tile__label">Total volume</div>
        <div className="ac-ao-kpi__tile__value">
          {kpis.totalVolume.toLocaleString()}
        </div>
        <FreshnessBadge freshnessAt={kpis.freshnessAt} />
      </div>

      <div className="ac-ao-kpi__tile" data-testid="kpi-tile-success-rate">
        <div className="ac-ao-kpi__tile__label">Success rate</div>
        <div className="ac-ao-kpi__tile__value">{formatPct(kpis.successRate)}</div>
        <FreshnessBadge freshnessAt={kpis.freshnessAt} />
      </div>

      <div className="ac-ao-kpi__tile" data-testid="kpi-tile-p95-latency">
        <div className="ac-ao-kpi__tile__label">P95 latency</div>
        <div className="ac-ao-kpi__tile__value">{formatMs(kpis.p95LatencyMs)}</div>
        <FreshnessBadge freshnessAt={kpis.freshnessAt} />
      </div>

      <div className="ac-ao-kpi__tile" data-testid="kpi-tile-total-cost">
        <div className="ac-ao-kpi__tile__label">Total cost (est.)</div>
        <div className="ac-ao-kpi__tile__value">{formatUsd(kpis.totalCostUsd)}</div>
        <FreshnessBadge freshnessAt={kpis.freshnessAt} />
      </div>
    </div>
  )
}

export default KPITiles
