/**
 * CommandCenter — REQ-044 FR-003 / US1.
 *
 * Phase 1 IA-only placeholder. The actual decision-queue rendering
 * is delivered in Phase 2. This component provides a stable landing
 * target so the index route (`/admin-console`) can redirect to
 * `command-center` and the sidebar's first item is non-empty.
 */
export function CommandCenter() {
  return (
    <div className="ac-page" data-testid="command-center">
      <div className="ac-page__header">
        <h1 className="ac-page__title">Command Center</h1>
        <span className="ac-page__hint">
          PM 决策指挥中心 · 默认 landing
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
          Command Center · 决策队列
        </div>
        <div style={{ fontSize: 12 }}>
          Phase 2 接入 decision signal（产品健康 / AI 质量 / 成本 / 系统健康 /
          incidents / 数据新鲜度）
        </div>
      </div>
    </div>
  )
}

export default CommandCenter