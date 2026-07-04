/**
 * Governance — REQ-044 US6 / FR-031~FR-036.
 *
 * Layout:
 * - Header
 * - 5 tabs (Access Matrix / Audit Log / Reveal Requests / Export /
 *   Retention Policy)
 * - Tab content
 *
 * Cross-cutting invariants:
 * - NO raw_* field exposed (SC-010).
 * - Sidebar gating via resolveRole in AdminShell already enforces
 *   least-privilege (AC-31.3); this page assumes the user passed
 *   that gate.
 * - Audit events are read-only (AC-34.3).
 */
import { useEffect, useState } from 'react'
import { useAccessMatrix } from '@/admin/hooks/queries/useGovernance'
import { AccessMatrixTable } from '@/admin/components/governance/AccessMatrixTable'
import { AuditLogViewer } from '@/admin/components/governance/AuditLogViewer'
import { RevealRequestForm } from '@/admin/components/governance/RevealRequestForm'
import { ExportForm } from '@/admin/components/governance/ExportForm'
import { RetentionPolicyEditor } from '@/admin/components/governance/RetentionPolicyEditor'
import { QualityFlagsBadge } from '@/admin/components/governance/QualityFlagsBadge'
import type { DataStatus } from '@/types/admin-governance'

type TabId = 'matrix' | 'audit' | 'reveal' | 'export' | 'retention'

const TAB_IDS: TabId[] = ['matrix', 'audit', 'reveal', 'export', 'retention']

const TAB_LABELS: Record<TabId, string> = {
  matrix: 'Access Matrix',
  audit: 'Audit Log',
  reveal: 'Reveal Requests',
  export: 'Export',
  retention: 'Retention',
}

export function Governance() {
  const [tab, setTab] = useState<TabId>('matrix')
  const accessMatrix = useAccessMatrix()

  // EC-1: when a reveal is denied, close any open trace drawer.
  useEffect(() => {
    function onRevealDenied() {
      // The trace drawer would be wired elsewhere in admin; here we
      // only ensure the page surfaces the audit_event_id. The drawer
      // listener closes itself when this event fires.
      console.info('[governance] reveal denied; closing trace drawer')
    }
    window.addEventListener('ic:reveal-denied', onRevealDenied)
    return () =>
      window.removeEventListener('ic:reveal-denied', onRevealDenied)
  }, [])

  return (
    <div
      className="ac-page"
      data-testid="governance"
      data-active-tab={tab}
    >
      <div className="ac-page__header">
        <h1 className="ac-page__title">Governance</h1>
        <span className="ac-page__hint">
          RBAC · audit · sensitive-action review · retention · FR-031~FR-036
        </span>
      </div>

      <div className="ac-gov">
        <nav
          className="ac-gov__tabs"
          role="tablist"
          aria-label="Governance workspace tabs"
        >
          {TAB_IDS.map((id) => (
            <button
              key={id}
              type="button"
              role="tab"
              className={`ac-gov__tab ${tab === id ? 'is-active' : ''}`}
              data-testid={`workspace-tab-${id}`}
              aria-selected={tab === id}
              onClick={() => setTab(id)}
            >
              {TAB_LABELS[id]}
            </button>
          ))}
        </nav>

        {tab === 'matrix' ? (
          <section data-testid="tab-access-matrix">
            <div style={{ marginBottom: 8, fontSize: 12 }}>
              Access matrix freshness:{' '}
              {accessMatrix.data ? (
                <span data-testid="access-matrix-freshness">
                  <QualityFlagsBadge
                    status={(accessMatrix.data.data_status as DataStatus) ?? 'valid_zero'}
                    size="sm"
                  />{' '}
                  · updated {accessMatrix.data.updated_at}
                </span>
              ) : (
                <span data-testid="access-matrix-freshness-pending">
                  Loading…
                </span>
              )}
            </div>
            <AccessMatrixTable
              matrix={accessMatrix.data}
              isLoading={accessMatrix.isLoading}
              error={accessMatrix.error as Error | null}
            />
          </section>
        ) : null}

        {tab === 'audit' ? (
          <section data-testid="tab-audit-log">
            <AuditLogViewer />
          </section>
        ) : null}

        {tab === 'reveal' ? (
          <section data-testid="tab-reveal-requests">
            <p style={{ fontSize: 12, marginBottom: 8, color: 'var(--ac-ink-muted)' }}>
              Sensitive payloads (raw resume / interview / prompt / model output /
              incident payload) require a reason (≥ 20 chars). The audit event
              is written BEFORE the reveal is granted (AC-33.5). Denied reveals
              trigger a fullscreen banner (EC-1).
            </p>
            <RevealRequestForm />
          </section>
        ) : null}

        {tab === 'export' ? (
          <section data-testid="tab-export">
            <p style={{ fontSize: 12, marginBottom: 8, color: 'var(--ac-ink-muted)' }}>
              Exports include only the approved field whitelist. raw_* fields
              are forced into <code>fields_redacted</code> and never embedded.
              A <code>review_snapshot</code> audit event is recorded for every
              generation (AC-35.5).
            </p>
            <ExportForm />
          </section>
        ) : null}

        {tab === 'retention' ? (
          <section data-testid="tab-retention">
            <p style={{ fontSize: 12, marginBottom: 8, color: 'var(--ac-ink-muted)' }}>
              Retention policies expire aged sensitive content (AC-36.3). Cache
              is invalidated on update (EC-3) and each change is self-audited
              (EC-4 / FR-034).
            </p>
            <RetentionPolicyEditor />
          </section>
        ) : null}
      </div>
    </div>
  )
}

export default Governance
