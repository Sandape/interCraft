/**
 * DecisionSignalCard — REQ-044 US1 / FR-007 + FR-008 + FR-009.
 *
 * Single-row rendering for the command-center decision queue.
 *
 * Shows: category icon, severity color, confidence badge, freshness
 * timestamp, title, owner, next-review CTA.
 *
 * Click → opens the DecisionSignalDrawer with full detail (FR-008 10
 * fields).
 */
import type { DecisionSignal, DecisionSignalCategory } from '@/types/admin-decision-signals'
import { ConfidenceBadge } from './ConfidenceBadge'
import { SeverityIcon } from './SeverityIcon'

interface DecisionSignalCardProps {
  signal: DecisionSignal
  onOpen: (signal: DecisionSignal) => void
}

const CATEGORY_ICON: Record<DecisionSignalCategory, string> = {
  product: '◎', // product
  'ai-quality': '✦', // sparkle
  'ai-cost': '◇', // cost
  'system-health': '⚙', // gear
  incident: '⚠', // warning
  'data-quality': '⌖', // data
}

const CATEGORY_LABEL: Record<DecisionSignalCategory, string> = {
  product: 'Product',
  'ai-quality': 'AI Quality',
  'ai-cost': 'AI Cost',
  'system-health': 'System',
  incident: 'Incident',
  'data-quality': 'Data Quality',
}

function formatFreshness(ts: string): string {
  if (ts === 'unknown') return 'stale'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function DecisionSignalCard({ signal, onOpen }: DecisionSignalCardProps) {
  const isStale =
    signal.qualityFlags.stale ||
    signal.freshnessAt === 'unknown'
  const isPartialBaseline = signal.qualityFlags.partialBaseline

  return (
    <button
      type="button"
      className="ds-card"
      data-testid={`decision-signal-card-${signal.id}`}
      data-signal-id={signal.id}
      data-signal-severity={signal.severity}
      data-signal-confidence={signal.confidence}
      data-signal-category={signal.category}
      onClick={() => onOpen(signal)}
    >
      <div className="ds-card__left">
        <span
          className={`ds-card__category ds-card__category--${signal.category}`}
          title={`Category: ${CATEGORY_LABEL[signal.category]}`}
          aria-label={`Category ${CATEGORY_LABEL[signal.category]}`}
        >
          {CATEGORY_ICON[signal.category]}
        </span>
        <SeverityIcon severity={signal.severity} />
      </div>
      <div className="ds-card__body">
        <div className="ds-card__title-row">
          <span className="ds-card__title">{signal.title}</span>
          <ConfidenceBadge tier={signal.confidence} />
        </div>
        <div className="ds-card__meta">
          <span className="ds-card__owner" data-testid="owner">
            {signal.owner}
          </span>
          <span className="ds-card__dot">·</span>
          <span
            className={`ds-card__freshness ${isStale ? 'ds-card__freshness--stale' : ''}`}
            data-testid="freshness"
            data-stale={isStale ? 'true' : 'false'}
          >
            {isStale ? 'stale · ' : ''}
            {formatFreshness(signal.freshnessAt)}
          </span>
          {isPartialBaseline ? (
            <>
              <span className="ds-card__dot">·</span>
              <span
                className="ds-card__partial-baseline"
                data-testid="partial-baseline"
              >
                partial baseline
              </span>
            </>
          ) : null}
        </div>
      </div>
      <div className="ds-card__right">
        <span className="ds-card__next-review">Next review →</span>
      </div>
    </button>
  )
}

export default DecisionSignalCard