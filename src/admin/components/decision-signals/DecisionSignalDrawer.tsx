/**
 * DecisionSignalDrawer — REQ-044 US1 / FR-008.
 *
 * Detail panel showing all 10 FR-008 fields plus evidence_links
 * (FR-018), quality_flags (FR-028), and the sort-key metadata.
 *
 * Open via DecisionSignalCard click; close via the X button or
 * Escape key.
 */
import { useEffect } from 'react'
import type { DecisionSignal } from '@/types/admin-decision-signals'
import { ConfidenceBadge } from './ConfidenceBadge'
import { SeverityIcon } from './SeverityIcon'

interface DecisionSignalDrawerProps {
  signal: DecisionSignal | null
  onClose: () => void
}

const CATEGORY_LABEL: Record<DecisionSignal['category'], string> = {
  product: 'Product',
  'ai-quality': 'AI Quality',
  'ai-cost': 'AI Cost',
  'system-health': 'System Health',
  incident: 'Incident',
  'data-quality': 'Data Quality',
}

function formatFull(ts: string): string {
  if (ts === 'unknown') return 'unknown (stale)'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  return d.toLocaleString()
}

export function DecisionSignalDrawer({ signal, onClose }: DecisionSignalDrawerProps) {
  useEffect(() => {
    if (!signal) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [signal, onClose])

  if (!signal) return null

  return (
    <>
      <div
        className="ds-drawer__backdrop"
        data-testid="decision-signal-drawer-backdrop"
        onClick={onClose}
      />
      <aside
        className="ds-drawer"
        data-testid="decision-signal-drawer"
        data-signal-id={signal.id}
        role="dialog"
        aria-label={`Decision signal ${signal.id}`}
      >
        <header className="ds-drawer__header">
          <div className="ds-drawer__header-row">
            <SeverityIcon severity={signal.severity} />
            <h2 className="ds-drawer__title">{signal.title}</h2>
            <button
              type="button"
              className="ds-drawer__close"
              onClick={onClose}
              data-testid="decision-signal-drawer-close"
              aria-label="Close"
            >
              ×
            </button>
          </div>
          <div className="ds-drawer__meta-row">
            <span className="ds-drawer__category">
              {CATEGORY_LABEL[signal.category]}
            </span>
            <ConfidenceBadge tier={signal.confidence} />
            <span
              className={`ds-drawer__freshness ${
                signal.qualityFlags.stale || signal.freshnessAt === 'unknown'
                  ? 'ds-drawer__freshness--stale'
                  : ''
              }`}
              data-testid="drawer-freshness"
            >
              {formatFull(signal.freshnessAt)}
            </span>
          </div>
        </header>

        <dl className="ds-drawer__fields">
          <dt data-testid="field-what-changed">What changed</dt>
          <dd>{signal.whatChanged}</dd>

          <dt data-testid="field-affected-segment">Affected segment</dt>
          <dd>{signal.affectedSegment}</dd>

          <dt data-testid="field-comparison-baseline">Comparison baseline</dt>
          <dd>
            {signal.comparisonBaseline}
            {signal.qualityFlags.partialBaseline ? (
              <span
                className="ds-drawer__chip ds-drawer__chip--warn"
                data-testid="drawer-partial-baseline"
              >
                partial baseline
              </span>
            ) : null}
          </dd>

          <dt data-testid="field-severity">Severity</dt>
          <dd>{signal.severity}</dd>

          <dt data-testid="field-confidence">Confidence</dt>
          <dd>{signal.confidence}</dd>

          <dt data-testid="field-owner">Owner</dt>
          <dd>{signal.owner}</dd>

          <dt data-testid="field-freshness-at">Freshness at</dt>
          <dd>{formatFull(signal.freshnessAt)}</dd>

          <dt data-testid="field-next-review-link">Next review</dt>
          <dd>
            <a
              href={signal.nextReviewLink}
              className="ds-drawer__link"
              data-testid="drawer-next-review-link"
            >
              {signal.nextReviewLink}
            </a>
          </dd>

          <dt data-testid="field-evidence-links">Evidence links</dt>
          <dd>
            {signal.evidenceLinks.length === 0 ? (
              <span className="ds-drawer__empty">No evidence links yet</span>
            ) : (
              <ul className="ds-drawer__evidence-list">
                {signal.evidenceLinks.map((ev, idx) => (
                  <li key={`${signal.id}-ev-${idx}`}>
                    <a href={ev.href} data-kind={ev.kind}>
                      [{ev.kind}] {ev.label}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </dd>

          {signal.qualityFlags.stale ||
          signal.qualityFlags.partialBaseline ||
          signal.qualityFlags.delayedIngestion ||
          signal.qualityFlags.missingVersionFields.length > 0 ||
          signal.qualityFlags.partialData ? (
            <>
              <dt data-testid="field-quality-flags">Quality flags</dt>
              <dd>
                <ul className="ds-drawer__flags">
                  {signal.qualityFlags.stale ? (
                    <li data-testid="quality-flag-stale">stale</li>
                  ) : null}
                  {signal.qualityFlags.partialBaseline ? (
                    <li data-testid="quality-flag-partial-baseline">
                      partial baseline
                    </li>
                  ) : null}
                  {signal.qualityFlags.delayedIngestion ? (
                    <li>delayed ingestion</li>
                  ) : null}
                  {signal.qualityFlags.missingVersionFields.length > 0 ? (
                    <li>
                      missing version fields:{' '}
                      {signal.qualityFlags.missingVersionFields.join(', ')}
                    </li>
                  ) : null}
                  {signal.qualityFlags.partialData ? <li>partial data</li> : null}
                </ul>
              </dd>
            </>
          ) : null}
        </dl>

        <footer className="ds-drawer__footer">
          <a
            href={signal.nextReviewLink}
            className="ds-drawer__cta"
            data-testid="drawer-next-review-cta"
          >
            Open next review
          </a>
        </footer>
      </aside>
    </>
  )
}

export default DecisionSignalDrawer