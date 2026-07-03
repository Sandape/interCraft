/**
 * AIOperations — REQ-044 FR-005 / US3.
 *
 * Phase 1 placeholder. Phase 2 delivers AI quality / cost / latency /
 * eval / badcase / model-version deltas per spec US3.
 */
export function AIOperations() {
  return (
    <div className="ac-page" data-testid="ai-operations">
      <div className="ac-page__header">
        <h1 className="ac-page__title">AI Operations</h1>
        <span className="ac-page__hint">
          AI 质量 · 成本 · 时延 · 评测 · Badcase
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
          AI Operations · Phase 2
        </div>
        <div style={{ fontSize: 12 }}>
          该模块正在迭代中。本批次仅交付 IA shell。
        </div>
      </div>
    </div>
  )
}

export default AIOperations