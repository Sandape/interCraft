/**
 * IncidentDrawer — REQ-044 US4 / FR-021 + FR-022 + AC-22.3.
 *
 * Side-panel detail with 3 tabs:
 *
 *   1. Overview    — 10 FR-021 fields + EC-2/3/4 fields
 *   2. Evidence    — 8-type evidence list (FR-022 + AC-22.1)
 *   3. Comments    — comment thread (FR-022 + AC-22.3)
 *
 * Plus a footer "Change status" form (EC-4) when the current role
 * holds INCIDENT_CHANGE.
 */
import { useState } from 'react'
import type {
  EvidenceLink,
  Incident,
  IncidentStatus,
} from '@/types/admin-incidents'
import {
  useIncidentEvidence,
  useIncidentComments,
  useAddIncidentComment,
  useChangeIncidentStatus,
} from '@/admin/hooks/queries/useIncidents'
import { EvidenceLinkList } from './EvidenceLinkList'
import { CommentList } from './CommentList'
import { SeverityBadge } from './SeverityBadge'
import { TrendArrow } from './TrendArrow'

type Tab = 'overview' | 'evidence' | 'comments'

interface IncidentDrawerProps {
  incident: Incident | null
  onClose: () => void
  /** Capabilities the current role holds (page-level). */
  canChange: boolean
  canComment: boolean
}

const STATUS_OPTIONS: IncidentStatus[] = [
  'open',
  'investigating',
  'resolved',
  'postmortem',
]

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

export function IncidentDrawer({
  incident,
  onClose,
  canChange,
  canComment,
}: IncidentDrawerProps) {
  const [tab, setTab] = useState<Tab>('overview')
  const [newStatus, setNewStatus] = useState<IncidentStatus>('investigating')
  const [newOwner, setNewOwner] = useState('')
  const [changeReason, setChangeReason] = useState('')

  const evidenceQuery = useIncidentEvidence(incident?.id ?? null)
  const commentsQuery = useIncidentComments(incident?.id ?? null)
  const addComment = useAddIncidentComment(incident?.id ?? '')
  const changeStatus = useChangeIncidentStatus(incident?.id ?? '')

  if (!incident) return null

  const onOpenEvidence = (link: EvidenceLink) => {
    // SC-007 3-min drilldown surface: dispatch a CustomEvent that the
    // page can intercept to navigate to the deep-link route without
    // actually leaving the SPA shell. Playwright can observe the
    // event to verify the 8-type coverage.
    window.dispatchEvent(
      new CustomEvent('ic:open-evidence', { detail: link }),
    )
  }

  const onSubmitStatus = async () => {
    if (!changeReason.trim()) return
    await changeStatus.mutateAsync({
      newStatus,
      newOwner: newOwner.trim() || null,
      reason: changeReason.trim(),
    })
    setChangeReason('')
    setNewOwner('')
  }

  return (
    <aside
      className="ic-drawer"
      data-testid="incident-drawer"
      data-incident-id={incident.id}
      role="dialog"
      aria-label={`Incident ${incident.id}`}
    >
      <header className="ic-drawer__header">
        <div className="ic-drawer__title-row">
          <SeverityBadge severity={incident.severity} />
          <span className="ic-drawer__id">{incident.id}</span>
          <button
            type="button"
            className="ic-drawer__close"
            data-testid="drawer-close"
            onClick={onClose}
            aria-label="Close drawer"
          >
            ×
          </button>
        </div>
        <h2 className="ic-drawer__title">{incident.title}</h2>
        {incident.candidate ? (
          <span
            className="ic-drawer__candidate"
            data-testid="drawer-candidate-label"
          >
            candidate · low confidence (EC-1)
          </span>
        ) : null}
        {incident.ingestionDelayed ? (
          <span
            className="ic-drawer__ingestion-delayed"
            data-testid="drawer-ingestion-delayed"
          >
            ingestion delayed (EC-3)
          </span>
        ) : null}
        <nav
          className="ic-drawer__tabs"
          role="tablist"
          aria-label="Incident detail tabs"
        >
          <button
            type="button"
            role="tab"
            className={`ic-drawer__tab ${tab === 'overview' ? 'is-active' : ''}`}
            data-testid="tab-overview"
            aria-selected={tab === 'overview'}
            onClick={() => setTab('overview')}
          >
            Overview
          </button>
          <button
            type="button"
            role="tab"
            className={`ic-drawer__tab ${tab === 'evidence' ? 'is-active' : ''}`}
            data-testid="tab-evidence"
            aria-selected={tab === 'evidence'}
            onClick={() => setTab('evidence')}
          >
            Evidence
          </button>
          <button
            type="button"
            role="tab"
            className={`ic-drawer__tab ${tab === 'comments' ? 'is-active' : ''}`}
            data-testid="tab-comments"
            aria-selected={tab === 'comments'}
            onClick={() => setTab('comments')}
          >
            Comments
            {commentsQuery.data ? (
              <span
                className="ic-drawer__tab-count"
                data-testid="tab-comments-count"
              >
                {commentsQuery.data.total}
              </span>
            ) : null}
          </button>
        </nav>
      </header>

      <div className="ic-drawer__body">
        {tab === 'overview' ? (
          <section
            className="ic-drawer__panel"
            data-testid="panel-overview"
          >
            <dl className="ic-drawer__defs">
              <div className="ic-drawer__def">
                <dt>Status</dt>
                <dd data-testid="overview-status">{incident.status}</dd>
              </div>
              <div className="ic-drawer__def">
                <dt>Owner</dt>
                <dd data-testid="overview-owner">{incident.owner}</dd>
              </div>
              <div className="ic-drawer__def">
                <dt>Trend</dt>
                <dd>
                  <TrendArrow trend={incident.trend} />
                  <span data-testid="overview-trend">{incident.trend}</span>
                </dd>
              </div>
              <div className="ic-drawer__def">
                <dt>Feature area</dt>
                <dd data-testid="overview-feature-area">
                  {incident.affectedFeatureArea}
                </dd>
              </div>
              <div className="ic-drawer__def">
                <dt>Journey step</dt>
                <dd data-testid="overview-journey">
                  {incident.affectedJourneyStep}
                </dd>
              </div>
              <div className="ic-drawer__def">
                <dt>First seen</dt>
                <dd data-testid="overview-first-seen">
                  {formatTime(incident.firstSeenAt)}
                </dd>
              </div>
              <div className="ic-drawer__def">
                <dt>Last seen</dt>
                <dd data-testid="overview-last-seen">
                  {formatTime(incident.lastSeenAt)}
                </dd>
              </div>
              <div className="ic-drawer__def">
                <dt>Affected count</dt>
                <dd data-testid="overview-affected-count">
                  {incident.affectedCount}
                </dd>
              </div>
              {incident.commonRootCause ? (
                <div
                  className="ic-drawer__def"
                  data-testid="overview-common-root-cause"
                >
                  <dt>Common root cause</dt>
                  <dd>
                    {incident.commonRootCause}
                    {incident.linkedIncidentIds.length > 0 ? (
                      <ul className="ic-drawer__linked">
                        {incident.linkedIncidentIds.map((id) => (
                          <li
                            key={id}
                            data-testid={`linked-incident-${id}`}
                          >
                            {id}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </dd>
                </div>
              ) : null}
            </dl>
            {incident.description ? (
              <p
                className="ic-drawer__description"
                data-testid="overview-description"
              >
                {incident.description}
              </p>
            ) : null}
            {canChange ? (
              <div
                className="ic-drawer__change-status"
                data-testid="change-status-form"
              >
                <h3 className="ic-drawer__change-status-title">
                  Change status (EC-4)
                </h3>
                <label className="ic-drawer__field">
                  <span>New status</span>
                  <select
                    data-testid="change-status-new"
                    value={newStatus}
                    onChange={(e) =>
                      setNewStatus(e.target.value as IncidentStatus)
                    }
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ic-drawer__field">
                  <span>New owner (optional)</span>
                  <input
                    data-testid="change-status-owner"
                    value={newOwner}
                    onChange={(e) => setNewOwner(e.target.value)}
                    placeholder="@ops-oncall"
                  />
                </label>
                <label className="ic-drawer__field">
                  <span>Reason</span>
                  <input
                    data-testid="change-status-reason"
                    value={changeReason}
                    onChange={(e) => setChangeReason(e.target.value)}
                    placeholder="Why are you changing status?"
                  />
                </label>
                <button
                  type="button"
                  className="ic-drawer__change-status-submit"
                  data-testid="change-status-submit"
                  onClick={onSubmitStatus}
                  disabled={
                    changeStatus.isPending || !changeReason.trim()
                  }
                >
                  {changeStatus.isPending
                    ? 'Submitting…'
                    : 'Submit status change'}
                </button>
              </div>
            ) : null}
          </section>
        ) : null}

        {tab === 'evidence' ? (
          <section
            className="ic-drawer__panel"
            data-testid="panel-evidence"
          >
            {evidenceQuery.isLoading ? (
              <p data-testid="evidence-loading">Loading evidence…</p>
            ) : evidenceQuery.isError ? (
              <p className="ac-error-banner" data-testid="evidence-error">
                Failed to load evidence
              </p>
            ) : evidenceQuery.data ? (
              <EvidenceLinkList
                links={evidenceQuery.data.evidenceLinks}
                coverage={evidenceQuery.data.coverage}
                onOpenEvidence={onOpenEvidence}
              />
            ) : null}
          </section>
        ) : null}

        {tab === 'comments' ? (
          <section
            className="ic-drawer__panel"
            data-testid="panel-comments"
          >
            {commentsQuery.isLoading ? (
              <p data-testid="comments-loading">Loading comments…</p>
            ) : commentsQuery.isError ? (
              <p className="ac-error-banner" data-testid="comments-error">
                Failed to load comments
              </p>
            ) : commentsQuery.data ? (
              <CommentList
                comments={commentsQuery.data.comments}
                canAdd={canComment}
                onAdd={(body) => addComment.mutateAsync(body)}
                isSubmitting={addComment.isPending}
              />
            ) : null}
          </section>
        ) : null}
      </div>
    </aside>
  )
}

export default IncidentDrawer
