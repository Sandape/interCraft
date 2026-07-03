/**
 * Placeholder — coming-soon pages for the admin sidebar.
 */
export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="ac-page">
      <div className="ac-page__header">
        <h1 className="ac-page__title">{title}</h1>
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
          {title} · 敬请期待
        </div>
        <div style={{ fontSize: 12 }}>
          该模块正在迭代中。本批次仅交付 IA shell (Logs & Traces 业务由 LogCenter 承载)。
        </div>
      </div>
    </div>
  )
}
