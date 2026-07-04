/**
 * IncidentCard — REQ-044 US4 / FR-021 + AC-21.5.
 *
 * Single-row rendering for the incident queue. Shows 8 fields per
 * AC-21.5 + trend arrow + severity color. Candidate incidents get
 * an explicit "candidate" label (EC-1). Common root cause cross-
 * link is rendered as a chip (EC-2). Ingestion-delayed incidents
 * get an "ingestion delayed" label (EC-3).
 */
import type { Incident } from '@/types/admin-incidents'
import { SeverityBadge } from './SeverityBadge'
import { TrendArrow } from './TrendArrow'

interface IncidentCardProps {
  incident: Incident
  onOpen: (incident: Incident) => void
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

export function IncidentCard({ incident, onOpen }: IncidentCardProps) {
  return (
    <button
      type="button"
      className={`ic-card ${incident.candidate ? 'ic-card--candidate' : ''}`}
      data-testid={`incident-card-${incident.id}`}
      data-incident-id={incident.id}
      data-incident-severity={incident.severity}
      data-incident-status={incident.status}
      data-incident-trend={incident.trend}
      data-incident-candidate={incident.candidate ? 'true' : 'false'}
      onClick={() => onOpen(incident)}
    >
      <div className="ic-card__left">
        <SeverityBadge severity={incident.severity} />
        <TrendArrow trend={incident.trend} />
      </div>
      <div className="ic-card__body">
        <div className="ic-card__title-row">
          <span className="ic-card__title">{incident.title}</span>
          {incident.candidate ? (
            <span
              className="ic-card__candidate-label"
              data-testid="candidate-label"
              title="EC-1: low confidence anomaly — not merged into confirmed incidents"
            >
              candidate
            </span>
          ) : null}
          {incident.ingestionDelayed ? (
            <span
              className="ic-card__ingestion-delayed"
              data-testid="ingestion-delayed"
              title="EC-3: data ingestion lag triggered this incident"
            >
              ingestion delayed
            </span>
          ) : null}
        </div>
        <div className="ic-card__meta">
          <span className="ic-card__owner">{incident.owner}</span>
          <span className="ic-card__dot">·</span>
          <span className="ic-card__feature">
            {incident.affectedFeatureArea}
          </span>
          <span className="ic-card__dot">·</span>
          <span className="ic-card__journey">
            {incident.affectedJourneyStep}
          </span>
          <span className="ic-card__dot">·</span>
          <span className="ic-card__freshness" data-testid="last-seen">
            last seen {formatTime(incident.lastSeenAt)}
          </span>
        </div>
        {incident.commonRootCause ? (
          <div className="ic-card__root-cause" data-testid="common-root-cause">
            <span className="ic-card__root-cause-label">common root cause:</span>
            <span className="ic-card__root-cause-value">
              {incident.commonRootCause}
            </span>
            <span className="ic-card__root-cause-siblings">
              ({incident.linkedIncidentIds.length} linked incident
              {incident.linkedIncidentIds.length === 1 ? '' : 's'})
            </span>
          </div>
        ) : null}
      </div>
      <div className="ic-card__right">
        <span className="ic-card__affected">
          {incident.affectedCount} affected
        </span>
        <span className="ic-card__next">Detail →</span>
      </div>
    </button>
  )
}

export default IncidentCard
