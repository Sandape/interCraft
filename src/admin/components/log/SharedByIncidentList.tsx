/**
 * SharedByIncidentList — REQ-044 US5 / EC-2.
 *
 * When multiple incidents share one technical root cause (Edge Cases
 * line 323), the log detail drawer surfaces a "Shared by" cross-link
 * list so the developer can pivot from one incident's trace to another
 * incident's evidence panel without re-typing ids.
 */
import { Link2 } from 'lucide-react'
import type { SharedByIncidentRef } from '@/types/admin-logs'

interface SharedByIncidentListProps {
  refs: SharedByIncidentRef[]
}

const SEVERITY_CLASS: Record<SharedByIncidentRef['severity'], string> = {
  P0: 'ac-severity--p0',
  P1: 'ac-severity--p1',
  P2: 'ac-severity--p2',
  P3: 'ac-severity--p3',
}

export function SharedByIncidentList({ refs }: SharedByIncidentListProps) {
  if (refs.length === 0) {
    return (
      <div
        className="ac-shared-by-incidents ac-shared-by-incidents--empty"
        data-testid="shared-by-incidents-empty"
      >
        <span className="ac-ink-muted">该 trace 未被多个 incident 共享</span>
      </div>
    )
  }
  return (
    <section
      className="ac-shared-by-incidents"
      data-testid="shared-by-incidents"
      data-count={refs.length}
    >
      <header className="ac-shared-by-incidents__head">
        <Link2 size={14} />
        <span>Shared by</span>
        <span
          className="ac-shared-by-incidents__count"
          data-testid="shared-by-incidents-count"
        >
          ({refs.length})
        </span>
      </header>
      <ul className="ac-shared-by-incidents__list">
        {refs.map((r) => (
          <li
            key={r.incidentId}
            className="ac-shared-by-incidents__item"
            data-testid={`shared-by-incident-${r.incidentId}`}
          >
            <span
              className={`ac-shared-by-incidents__severity ${SEVERITY_CLASS[r.severity]}`}
            >
              {r.severity}
            </span>
            <a
              href={r.href}
              className="ac-shared-by-incidents__link"
              data-testid={`shared-by-incident-link-${r.incidentId}`}
            >
              {r.title}
            </a>
            <span className="ac-shared-by-incidents__ref">
              ref: {r.incidentId}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default SharedByIncidentList