/**
 * AuditLogViewer — REQ-044 FR-034 / AC-34.2.
 *
 * Renders the audit-event buffer with the 7 locked fields per row:
 *
 *   actor / timestamp / target / action / reason / result / visibility_mode
 *
 * Per AC-34.3 the component exposes NO delete / edit affordance —
 * audit events are immutable in this release.
 *
 * Filters: optional ``actor`` substring search + ``action`` dropdown.
 * 11-action taxonomy (US1 + US4 + US6).
 */
import { useMemo, useState } from 'react'
import type {
  AuditAction,
  AuditEvent,
} from '@/types/admin-governance'
import { useAuditEvents } from '@/admin/hooks/queries/useGovernance'

const AUDIT_ACTIONS: AuditAction[] = [
  'replay_triggered',
  'diff_computed',
  'tag_added',
  'tag_removed',
  'incident_status_changed',
  'incident_comment_added',
  'badcase_status_changed',
  'badcase_escalated',
  'sensitive_reveal',
  'export',
  'review_snapshot',
]

export function AuditLogViewer() {
  const [actorFilter, setActorFilter] = useState<string>('')
  const [actionFilter, setActionFilter] = useState<AuditAction | ''>('')

  const filters = useMemo(
    () => ({
      actor: actorFilter || undefined,
      action: actionFilter || undefined,
    }),
    [actorFilter, actionFilter],
  )

  const q = useAuditEvents(filters)

  if (q.isLoading) {
    return (
      <div
        className="ac-gov-audit"
        data-testid="audit-log-loading"
        role="status"
      >
        Loading audit log…
      </div>
    )
  }

  if (q.isError) {
    return (
      <div
        className="ac-error-banner"
        data-testid="audit-log-error"
        role="alert"
      >
        Failed to load audit log.
      </div>
    )
  }

  const events = q.data?.events ?? []

  return (
    <div
      className="ac-gov-audit"
      data-testid="audit-log-viewer"
      data-event-count={events.length}
    >
      <div
        style={{
          display: 'flex',
          gap: 12,
          padding: 12,
          borderBottom: '1px solid var(--ac-border-subtle)',
          alignItems: 'center',
        }}
      >
        <input
          data-testid="audit-filter-actor"
          placeholder="filter by actor..."
          value={actorFilter}
          onChange={(e) => setActorFilter(e.target.value)}
          style={{
            padding: '4px 8px',
            border: '1px solid var(--ac-border-subtle)',
            borderRadius: 4,
            fontSize: 12,
          }}
        />
        <select
          data-testid="audit-filter-action"
          value={actionFilter}
          onChange={(e) =>
            setActionFilter((e.target.value as AuditAction) || '')
          }
          style={{
            padding: '4px 8px',
            border: '1px solid var(--ac-border-subtle)',
            borderRadius: 4,
            fontSize: 12,
          }}
        >
          <option value="">all actions</option>
          {AUDIT_ACTIONS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <span style={{ fontSize: 11, color: 'var(--ac-ink-faint)' }}>
          {events.length} event{events.length === 1 ? '' : 's'} (read-only)
        </span>
      </div>

      <div
        className="ac-gov-audit__row ac-gov-audit__row--header"
        data-testid="audit-log-header"
      >
        <span>actor</span>
        <span>timestamp</span>
        <span>action</span>
        <span>target</span>
        <span>reason</span>
        <span>result</span>
        <span>visibility</span>
      </div>

      {events.length === 0 ? (
        <div
          className="ac-gov-audit__empty"
          data-testid="audit-log-empty"
        >
          No audit events match the current filter.
        </div>
      ) : (
        events.map((ev: AuditEvent) => (
          <div
            key={ev.event_id}
            className="ac-gov-audit__row"
            data-testid="audit-event"
            data-action={ev.action}
            data-result={ev.result}
          >
            <span className="ac-gov-audit__actor">{ev.actor}</span>
            <span>{ev.timestamp}</span>
            <span className="ac-gov-audit__action">{ev.action}</span>
            <span>
              {ev.target_kind}
              {ev.target_id ? ` / ${ev.target_id}` : ''}
            </span>
            <span>{ev.reason ?? ''}</span>
            <span>{ev.result}</span>
            <span>{ev.visibility_mode}</span>
          </div>
        ))
      )}
    </div>
  )
}

export default AuditLogViewer
