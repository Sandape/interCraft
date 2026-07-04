/**
 * BadcaseDrawer — REQ-044 US4 / FR-023 + AC-23.3.
 *
 * 4-tab drawer for a single badcase:
 *
 *   1. Overview   — 10 FR-023 fields + audit trail summary
 *   2. Privacy    — privacy class + redaction policy explanation
 *   3. AI Task    — deep-link to the related AI task (US3 surface)
 *   4. Comments   — comment thread (shared with incident surface)
 *
 * Plus an "Escalate to Incident" button (AC-23.4) when the current
 * role holds BADCASE_CHANGE.
 */
import { useState } from 'react'
import type { Badcase, BadcasePrivacyClass } from '@/types/admin-incidents'
import { useEscalateBadcase } from '@/admin/hooks/queries/useIncidents'
import { CommentList } from './CommentList'

type Tab = 'overview' | 'privacy' | 'ai-task' | 'comments'

interface BadcaseDrawerProps {
  badcase: Badcase | null
  onClose: () => void
  canEscalate: boolean
}

const PRIVACY_DESCRIPTION: Record<BadcasePrivacyClass, string> = {
  public:
    'No sensitive content — safe to surface in PM views and exported snapshots.',
  internal:
    'Internal-only fields. Maintainer developers can reveal with a reason + audit.',
  restricted:
    'Maintainer-only. Reveal requires INCIDENT_CHANGE + reason + audit. Default UI redacts raw fields.',
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

export function BadcaseDrawer({ badcase, onClose, canEscalate }: BadcaseDrawerProps) {
  const [tab, setTab] = useState<Tab>('overview')
  const escalate = useEscalateBadcase()

  if (!badcase) return null

  const onEscalate = async () => {
    await escalate.mutateAsync(badcase.id)
  }

  return (
    <aside
      className="bc-drawer"
      data-testid="badcase-drawer"
      data-badcase-id={badcase.id}
      role="dialog"
      aria-label={`Badcase ${badcase.id}`}
    >
      <header className="bc-drawer__header">
        <div className="bc-drawer__title-row">
          <span
            className={`bc-drawer__eval-verdict bc-drawer__eval-verdict--${badcase.status}`}
            data-testid="drawer-eval-verdict"
          >
            {badcase.evalVerdict}
          </span>
          <span
            className={`bc-drawer__privacy bc-drawer__privacy--${badcase.privacyClass}`}
            data-testid="drawer-privacy-class"
            data-privacy-class={badcase.privacyClass}
          >
            {badcase.privacyClass}
          </span>
          <span className="bc-drawer__id">{badcase.id}</span>
          <button
            type="button"
            className="bc-drawer__close"
            data-testid="badcase-drawer-close"
            onClick={onClose}
            aria-label="Close drawer"
          >
            ×
          </button>
        </div>
        <h2 className="bc-drawer__title">{badcase.classification}</h2>
        <nav
          className="bc-drawer__tabs"
          role="tablist"
          aria-label="Badcase detail tabs"
        >
          <button
            type="button"
            role="tab"
            className={`bc-drawer__tab ${tab === 'overview' ? 'is-active' : ''}`}
            data-testid="tab-overview"
            aria-selected={tab === 'overview'}
            onClick={() => setTab('overview')}
          >
            Overview
          </button>
          <button
            type="button"
            role="tab"
            className={`bc-drawer__tab ${tab === 'privacy' ? 'is-active' : ''}`}
            data-testid="tab-privacy"
            aria-selected={tab === 'privacy'}
            onClick={() => setTab('privacy')}
          >
            Privacy
          </button>
          <button
            type="button"
            role="tab"
            className={`bc-drawer__tab ${tab === 'ai-task' ? 'is-active' : ''}`}
            data-testid="tab-ai-task"
            aria-selected={tab === 'ai-task'}
            onClick={() => setTab('ai-task')}
          >
            AI Task
          </button>
          <button
            type="button"
            role="tab"
            className={`bc-drawer__tab ${tab === 'comments' ? 'is-active' : ''}`}
            data-testid="tab-comments"
            aria-selected={tab === 'comments'}
            onClick={() => setTab('comments')}
          >
            Comments
          </button>
        </nav>
      </header>

      <div className="bc-drawer__body">
        {tab === 'overview' ? (
          <section
            className="bc-drawer__panel"
            data-testid="bc-panel-overview"
          >
            <dl className="bc-drawer__defs">
              <div className="bc-drawer__def">
                <dt>Status</dt>
                <dd data-testid="bc-overview-status">{badcase.status}</dd>
              </div>
              <div className="bc-drawer__def">
                <dt>Owner</dt>
                <dd data-testid="bc-overview-owner">{badcase.owner}</dd>
              </div>
              <div className="bc-drawer__def">
                <dt>Affected feature area</dt>
                <dd data-testid="bc-overview-feature">
                  {badcase.affectedFeatureArea}
                </dd>
              </div>
              <div className="bc-drawer__def">
                <dt>Affected user</dt>
                <dd data-testid="bc-overview-user">
                  {badcase.affectedUserId}
                </dd>
              </div>
              <div className="bc-drawer__def">
                <dt>First seen</dt>
                <dd data-testid="bc-overview-first-seen">
                  {formatTime(badcase.firstSeenAt)}
                </dd>
              </div>
              <div className="bc-drawer__def">
                <dt>Incident</dt>
                <dd data-testid="bc-overview-incident">
                  {badcase.incidentId ?? '—'}
                </dd>
              </div>
              <div className="bc-drawer__def">
                <dt>Resolution</dt>
                <dd data-testid="bc-overview-resolution">
                  {badcase.resolution || '—'}
                </dd>
              </div>
            </dl>
            {badcase.description ? (
              <p
                className="bc-drawer__description"
                data-testid="bc-overview-description"
              >
                {badcase.description}
              </p>
            ) : null}
            {canEscalate && badcase.status !== 'escalated' ? (
              <div className="bc-drawer__escalate" data-testid="escalate-section">
                <h3 className="bc-drawer__escalate-title">Escalate to incident</h3>
                <p className="bc-drawer__escalate-hint">
                  Promotes this badcase to a new incident. Requires BADCASE_CHANGE.
                </p>
                <button
                  type="button"
                  className="bc-drawer__escalate-button"
                  data-testid="escalate-button"
                  onClick={onEscalate}
                  disabled={escalate.isPending}
                >
                  {escalate.isPending
                    ? 'Escalating…'
                    : 'Escalate to Incident'}
                </button>
                {escalate.data ? (
                  <p
                    className="bc-drawer__escalate-result"
                    data-testid="escalate-result"
                  >
                    Created {escalate.data.incidentId} at{' '}
                    {formatTime(escalate.data.escalatedAt)}
                  </p>
                ) : null}
                {escalate.isError ? (
                  <p
                    className="ac-error-banner"
                    data-testid="escalate-error"
                  >
                    Failed to escalate
                  </p>
                ) : null}
              </div>
            ) : null}
          </section>
        ) : null}

        {tab === 'privacy' ? (
          <section
            className="bc-drawer__panel"
            data-testid="bc-panel-privacy"
          >
            <p
              className="bc-drawer__privacy-desc"
              data-testid="privacy-description"
            >
              {PRIVACY_DESCRIPTION[badcase.privacyClass]}
            </p>
            <ul
              className="bc-drawer__privacy-list"
              data-testid="privacy-policies"
            >
              <li>Raw resume content: hidden (FR-032)</li>
              <li>Raw interview answers: hidden (FR-032)</li>
              <li>Raw prompts / model outputs: hidden (FR-032)</li>
              <li>Eval verdict + classification: visible</li>
              <li>Affected feature area + owner: visible</li>
              <li>Affected user id: visible (US2 privacy-safe lookup)</li>
            </ul>
          </section>
        ) : null}

        {tab === 'ai-task' ? (
          <section
            className="bc-drawer__panel"
            data-testid="bc-panel-ai-task"
          >
            <p data-testid="ai-task-link-hint">
              Cross-link to the AI task that produced this badcase. US3
              surfaces the eval verdict + cost + latency in the AI
              Operations workspace.
            </p>
            <a
              className="bc-drawer__ai-task-link"
              data-testid="ai-task-link"
              href={`/admin-console/ai-operations?tab=eval&badcase=${encodeURIComponent(badcase.id)}&from=${encodeURIComponent(badcase.id)}`}
            >
              View related AI task in AI Operations →
            </a>
          </section>
        ) : null}

        {tab === 'comments' ? (
          <section
            className="bc-drawer__panel"
            data-testid="bc-panel-comments"
          >
            <CommentList
              comments={[]}  // Badcase comments not implemented in Phase 1 (FR-022 only spec'd for incident)
              canAdd={false}
              onAdd={() => undefined}
            />
            <p
              className="bc-drawer__comments-hint"
              data-testid="badcase-comments-hint"
            >
              [CROSS-TEAM-DEBT] Badcase comments land in Phase 2 batch 4
              together with the badcase review_queue.
            </p>
          </section>
        ) : null}
      </div>
    </aside>
  )
}

export default BadcaseDrawer
