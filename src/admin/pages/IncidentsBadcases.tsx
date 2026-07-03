/**
 * IncidentsBadcases — REQ-044 FR-005 / US4.
 *
 * Phase 1 placeholder. Phase 2 delivers incident review workflow
 * and badcase drilldown per spec US4.
 */
export function IncidentsBadcases() {
  // Phase 2: incident detail panel will render a "View Logs" button
  // that links to /admin-console/logs-and-traces?from=<incident-id>.
  // The IA shell reserves this entry point so the cross-workspace
  // drilldown contract (FR-024) has a stable surface.
  return (
    <div className="ac-page" data-testid="incidents-badcases">
      <div className="ac-page__header">
        <h1 className="ac-page__title">Incidents &amp; Badcases</h1>
        <span className="ac-page__hint">运营 triage · review workflow</span>
      </div>
      <div
        style={{
          padding: '60px 24px',
          border: '1px dashed var(--ac-border-subtle)',
          borderRadius: 6,
          textAlign: 'center',
          color: 'var(--ac-ink-faint)',
        }}
      >
        <div style={{ fontSize: 14, marginBottom: 8, color: 'var(--ac-ink-muted)' }}>
          Incidents &amp; Badcases · Phase 2
        </div>
        <div style={{ fontSize: 12 }}>
          该模块正在迭代中。本批次仅交付 IA shell。
        </div>
      </div>
    </div>
  )
}

export default IncidentsBadcases