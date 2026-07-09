/**
 * UsersAccounts — REQ-044 US2 / FR-015 / FR-032.
 *
 * Phase 2 implementation. Renders the user search input + the
 * privacy-safe detail drawer.
 *
 * Privacy guard (FR-032 + AC-15.4): this file MUST NOT contain any
 * reference to raw_resume / raw_interview_answer / raw_prompt /
 * raw_model_output. The CI grep gate enforces this literal rule.
 */
import { useState } from 'react'
import { useUserSafe } from '@/admin/hooks/queries/useUserSafe'
import { UserDetailDrawer } from '@/admin/components/users/UserDetailDrawer'

// Seed user IDs for the Phase 1 demo. Phase 2 batch 2 will replace
// this with a real user search endpoint that filters by email / role
// without exposing raw PII.
const SEED_USER_IDS = [
  '019ec1be-0000-7000-8000-000000000001',
  '019ec1be-0000-7000-8000-000000000002',
  '019ec1be-0000-7000-8000-000000000003',
]

export function UsersAccounts() {
  const [search, setSearch] = useState('')
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)

  const profileQuery = useUserSafe(selectedUserId)

  return (
    <div
      className="ac-page ac-pa-users-page"
      data-testid="users-accounts"
    >
      <div className="ac-page__header">
        <h1 className="ac-page__title">用户与账户</h1>
        <span className="ac-page__hint">
          隐私安全的用户与账户查询（默认隐藏敏感内容）
        </span>
      </div>

      <div className="ac-pa-users-page__layout">
        <main className="ac-pa-users-page__main">
          <div className="ac-pa-users-page__search">
            <label
              htmlFor="ac-pa-user-search"
              className="ac-pa-users-page__search-label"
            >
              按 user_id 搜索（演示阶段）
            </label>
            <input
              id="ac-pa-user-search"
              data-testid="user-search-input"
              className="ac-pa-users-page__search-input"
              type="text"
              placeholder="019ec1be-... user_id"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <ul
              className="ac-pa-users-page__results"
              data-testid="user-search-results"
            >
              {SEED_USER_IDS.filter((uid) =>
                search ? uid.toLowerCase().includes(search.toLowerCase()) : true,
              ).map((uid) => (
                <li
                  key={uid}
                  className={
                    uid === selectedUserId
                      ? 'ac-pa-users-page__result ac-pa-users-page__result--active'
                      : 'ac-pa-users-page__result'
                  }
                  data-testid={`user-search-result-${uid}`}
                >
                  <button
                    type="button"
                    onClick={() => setSelectedUserId(uid)}
                    className="ac-pa-users-page__result-button"
                  >
                    {uid}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </main>

        <aside
          className="ac-pa-users-page__drawer"
          data-testid="users-accounts-drawer"
        >
          {profileQuery.isLoading ? (
            <div data-testid="user-drawer-loading">加载中...</div>
          ) : profileQuery.isError ? (
            <div data-testid="user-drawer-error">加载失败或用户不存在</div>
          ) : (
            <UserDetailDrawer
              profile={profileQuery.data ?? null}
              onClose={() => setSelectedUserId(null)}
            />
          )}
        </aside>
      </div>
    </div>
  )
}

export default UsersAccounts