/**
 * Governance — REQ-044 FR-005 / US8.
 *
 * Phase 1 placeholder. Phase 2 delivers role-based access, audit
 * logs, sensitive-action reason capture, export controls, and
 * retention policy UI per spec US8.
 */
export function Governance() {
  return (
    <div className="ac-page" data-testid="governance">
      <div className="ac-page__header">
        <h1 className="ac-page__title">Governance</h1>
        <span className="ac-page__hint">
          RBAC · audit · sensitive-action review · retention
        </span>
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
          Governance · Phase 2
        </div>
        <div style={{ fontSize: 12 }}>
          该模块正在迭代中。本批次仅交付 IA shell。
        </div>
      </div>
    </div>
  )
}

export default Governance