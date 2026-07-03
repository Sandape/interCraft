/**
 * UsersAccounts — REQ-044 FR-005 / US6.
 *
 * Phase 1 placeholder. Phase 2 delivers privacy-safe user/account
 * lookup for support and operations per spec US6.
 */
export function UsersAccounts() {
  return (
    <div className="ac-page" data-testid="users-accounts">
      <div className="ac-page__header">
        <h1 className="ac-page__title">Users &amp; Accounts</h1>
        <span className="ac-page__hint">
          隐私安全的用户与账户查询（默认隐藏敏感内容）
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
          Users &amp; Accounts · Phase 2
        </div>
        <div style={{ fontSize: 12 }}>
          该模块正在迭代中。本批次仅交付 IA shell。
        </div>
      </div>
    </div>
  )
}

export default UsersAccounts