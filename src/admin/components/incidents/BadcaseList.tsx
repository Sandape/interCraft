/**
 * BadcaseList — REQ-044 US4 / FR-023 + AC-23.2.
 *
 * List rendering for the badcase queue. Each row carries the
 * eval_verdict badge + privacy_class indicator + status. Visually
 * mirrors IncidentCard but with badcase-specific fields.
 */
import type { Badcase, BadcasePrivacyClass } from '@/types/admin-incidents'

interface BadcaseListProps {
  badcases: Badcase[]
  onOpen: (badcase: Badcase) => void
}

const PRIVACY_GLYPH: Record<BadcasePrivacyClass, string> = {
  public: '◌',
  internal: '◐',
  restricted: '⛔',
}

const PRIVACY_LABEL: Record<BadcasePrivacyClass, string> = {
  public: 'Public',
  internal: 'Internal',
  restricted: 'Restricted',
}

function formatTime(ts: string): string {
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

export function BadcaseList({ badcases, onOpen }: BadcaseListProps) {
  return (
    <ul className="bc-list" data-testid="badcase-list">
      {badcases.map((bc) => (
        <li
          key={bc.id}
          className={`bc-list__item bc-list__item--${bc.status}`}
          data-testid={`badcase-card-${bc.id}`}
          data-badcase-id={bc.id}
          data-badcase-status={bc.status}
        >
          <button
            type="button"
            className="bc-list__button"
            onClick={() => onOpen(bc)}
          >
            <div className="bc-list__left">
              <span
                className={`bc-list__eval-verdict bc-list__eval-verdict--${bc.status}`}
                data-testid="eval-verdict"
              >
                {bc.evalVerdict}
              </span>
              <span
                className={`bc-list__privacy bc-list__privacy--${bc.privacyClass}`}
                data-testid="privacy-class"
                data-privacy-class={bc.privacyClass}
                title={`Privacy class: ${PRIVACY_LABEL[bc.privacyClass]}`}
              >
                <span aria-hidden="true">{PRIVACY_GLYPH[bc.privacyClass]}</span>
                <span className="bc-list__privacy-label">
                  {PRIVACY_LABEL[bc.privacyClass]}
                </span>
              </span>
            </div>
            <div className="bc-list__body">
              <div className="bc-list__title-row">
                <span className="bc-list__title">
                  {bc.classification}
                </span>
                <span className="bc-list__id">{bc.id}</span>
              </div>
              <div className="bc-list__meta">
                <span className="bc-list__owner">{bc.owner}</span>
                <span className="bc-list__dot">·</span>
                <span className="bc-list__feature">
                  {bc.affectedFeatureArea}
                </span>
                <span className="bc-list__dot">·</span>
                <span className="bc-list__first-seen">
                  first seen {formatTime(bc.firstSeenAt)}
                </span>
              </div>
              {bc.incidentId ? (
                <div className="bc-list__escalated">
                  escalated → {bc.incidentId}
                </div>
              ) : null}
            </div>
            <div className="bc-list__right">
              <span className="bc-list__next">Detail →</span>
            </div>
          </button>
        </li>
      ))}
    </ul>
  )
}

export default BadcaseList
