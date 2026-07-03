/**
 * Reports — REQ-044 FR-005 / US7.
 *
 * Phase 1 placeholder. Phase 2 delivers internal review snapshots
 * that preserve selected filters, metric definitions, freshness
 * warnings, annotations, and privacy-safe evidence per spec US7.
 */
export function Reports() {
  return (
    <div className="ac-page" data-testid="reports">
      <div className="ac-page__header">
        <h1 className="ac-page__title">Reports</h1>
        <span className="ac-page__hint">
          内部 review snapshot · saved views · 导出快照
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
          Reports · Phase 2
        </div>
        <div style={{ fontSize: 12 }}>
          该模块正在迭代中。本批次仅交付 IA shell。
        </div>
      </div>
    </div>
  )
}

export default Reports