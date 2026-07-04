/**
 * EvidenceLinkList — REQ-044 US4 / FR-022 + AC-22.4.
 *
 * 8-type evidence link list with empty-state badges for each type
 * the incident does not yet cover. Each link is a clickable <a> with
 * the cross-workspace deep link (US5 log/trace placeholder, US3
 * ai_task, US2 user, US6 release).
 */
import type { EvidenceLink, EvidenceLinkType } from '@/types/admin-incidents'

interface EvidenceLinkListProps {
  links: EvidenceLink[]
  coverage: Record<string, number>
  onOpenEvidence?: (link: EvidenceLink) => void
}

const ALL_TYPES: EvidenceLinkType[] = [
  'product_metric',
  'user_impact',
  'ai_task',
  'eval_case',
  'log',
  'trace',
  'release',
  'comment',
]

const TYPE_LABEL: Record<EvidenceLinkType, string> = {
  product_metric: 'Product metric',
  user_impact: 'User impact',
  ai_task: 'AI task',
  eval_case: 'Eval case',
  log: 'Log',
  trace: 'Trace',
  release: 'Release',
  comment: 'Comment',
}

const TYPE_GLYPH: Record<EvidenceLinkType, string> = {
  product_metric: '◐',
  user_impact: '◉',
  ai_task: '✦',
  eval_case: '◧',
  log: '≡',
  trace: '↗',
  release: '◈',
  comment: '✎',
}

export function EvidenceLinkList({
  links,
  coverage,
  onOpenEvidence,
}: EvidenceLinkListProps) {
  return (
    <div className="ic-evidence" data-testid="evidence-link-list">
      {ALL_TYPES.map((t) => {
        const count = coverage[t] ?? 0
        const typeLinks = links.filter((l) => l.type === t)
        return (
          <section
            key={t}
            className="ic-evidence__section"
            data-testid={`evidence-section-${t}`}
            data-evidence-type={t}
            data-evidence-count={count}
          >
            <header className="ic-evidence__header">
              <span
                className="ic-evidence__glyph"
                aria-hidden="true"
                data-testid={`evidence-glyph-${t}`}
              >
                {TYPE_GLYPH[t]}
              </span>
              <span className="ic-evidence__type-label">
                {TYPE_LABEL[t]}
              </span>
              <span className="ic-evidence__count">({count})</span>
            </header>
            {count === 0 ? (
              <p
                className="ic-evidence__empty"
                data-testid={`evidence-empty-${t}`}
              >
                No {TYPE_LABEL[t].toLowerCase()} linked yet
              </p>
            ) : (
              <ul className="ic-evidence__list">
                {typeLinks.map((link) => (
                  <li
                    key={`${link.type}-${link.referenceId}`}
                    className={`ic-evidence__item ic-evidence__item--${link.privacyClass}`}
                    data-testid={`evidence-link-${link.referenceId}`}
                    data-evidence-link-type={link.type}
                    data-evidence-privacy={link.privacyClass}
                  >
                    <a
                      className="ic-evidence__anchor"
                      href={link.href}
                      onClick={(e) => {
                        // Prevent navigation; surface to parent so the
                        // page-level drilldown can be exercised in
                        // Playwright without leaving the workspace.
                        e.preventDefault()
                        onOpenEvidence?.(link)
                      }}
                    >
                      <span className="ic-evidence__label">{link.label}</span>
                      {link.summary ? (
                        <span className="ic-evidence__summary">
                          {link.summary}
                        </span>
                      ) : null}
                      <span className="ic-evidence__ref">
                        ref: {link.referenceId}
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )
      })}
    </div>
  )
}

export default EvidenceLinkList
