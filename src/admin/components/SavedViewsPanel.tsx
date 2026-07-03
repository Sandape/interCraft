/**
 * SavedViewsPanel — REQ-044 FR-006 stub.
 *
 * Phase 1 placeholder UI. The data layer (savedViewRepository) is
 * stubbed in src/repositories/savedViewRepository.ts — every method
 * throws NotImplementedError until Phase 2 US-CROSS delivers real
 * persistence. This component intentionally renders a static "coming
 * soon" surface rather than calling the repository, so the page is
 * never empty (no silent fallback).
 */
export function SavedViewsPanel() {
  return (
    <div
      className="ac-saved-views-panel"
      data-testid="saved-views-panel"
      style={{
        padding: 16,
        border: '1px dashed var(--ac-border-subtle)',
        borderRadius: 6,
        color: 'var(--ac-ink-faint)',
        fontSize: 12,
      }}
    >
      <div style={{ fontSize: 13, marginBottom: 6, color: 'var(--ac-ink-muted)' }}>
        Saved Views
      </div>
      <div>
        跨工作空间 saved views 在 Phase 2 (US-CROSS) 落地。底层
        savedViewRepository 当前强制 throw NotImplementedError, 防止
        silent fallback (铁律 A)。
      </div>
    </div>
  )
}

export default SavedViewsPanel