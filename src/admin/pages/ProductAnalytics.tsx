/**
 * ProductAnalytics — REQ-044 FR-005 / US2.
 *
 * Phase 1 placeholder. Phase 2 delivers funnel / cohort / retention /
 * feature-adoption views per spec US2.
 */
export function ProductAnalytics() {
  return (
    <div className="ac-page" data-testid="product-analytics">
      <div className="ac-page__header">
        <h1 className="ac-page__title">Product Analytics</h1>
        <span className="ac-page__hint">funnel · cohort · retention · adoption</span>
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
          Product Analytics · Phase 2
        </div>
        <div style={{ fontSize: 12 }}>
          该模块正在迭代中。本批次仅交付 IA shell。
        </div>
      </div>
    </div>
  )
}

export default ProductAnalytics