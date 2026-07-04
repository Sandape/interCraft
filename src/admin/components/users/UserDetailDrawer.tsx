/**
 * UserDetailDrawer — REQ-044 US2 / FR-015 / FR-032.
 *
 * Renders the privacy-safe profile for a user. Each field is
 * tagged with its visibility level (full / masked / hidden) so PM
 * can tell at a glance which fields are visible to their role
 * (FR-031 least-privilege, AC-15.3).
 *
 * Privacy guard: the component MUST NOT include any field named
 * raw_resume / raw_interview_answer / raw_prompt / raw_model_output
 * (FR-032 + AC-15.4).
 */
import type { UserPrivacySafe } from '@/types/admin-product-analytics'

interface UserDetailDrawerProps {
  profile: UserPrivacySafe | null
  onClose: () => void
}

const FIELD_LABEL: Record<string, string> = {
  email: 'Email',
  role: 'Role',
  journey_summary: 'Journey summary',
  incidents_count: 'Incidents',
  quality_score: 'Quality score',
  created_at: 'Created at',
  last_active_at: 'Last active',
}

function visibilityGlyph(level: 'full' | 'masked' | 'hidden'): string {
  if (level === 'full') return '👁'
  if (level === 'masked') return '◐'
  return '✕'
}

function visibilityLabel(level: 'full' | 'masked' | 'hidden'): string {
  if (level === 'full') return 'full'
  if (level === 'masked') return 'masked'
  return 'hidden'
}

export function UserDetailDrawer({ profile, onClose }: UserDetailDrawerProps) {
  if (!profile) {
    return (
      <div
        className="ac-pa-user-drawer ac-pa-user-drawer--empty"
        data-testid="user-drawer-empty"
        role="dialog"
        aria-label="User detail drawer"
      >
        <div className="ac-pa-user-drawer__empty-msg">
          选择一个 user_id 以查看隐私安全档案
        </div>
      </div>
    )
  }

  return (
    <div
      className="ac-pa-user-drawer"
      data-testid="user-drawer"
      role="dialog"
      aria-label="User detail drawer"
    >
      <div className="ac-pa-user-drawer__header">
        <span
          className="ac-pa-user-drawer__user-id"
          data-testid="user-drawer-user-id"
        >
          {profile.userId}
        </span>
        <button
          type="button"
          className="ac-pa-user-drawer__close"
          data-testid="user-drawer-close"
          onClick={onClose}
        >
          关闭
        </button>
      </div>

      <div className="ac-pa-user-drawer__meta">
        <span data-testid="user-drawer-cohort-population">
          cohort population {profile.cohortPopulation.toLocaleString()}
        </span>
        <span data-testid="user-drawer-last-computed-at">
          last computed {profile.lastComputedAt}
        </span>
        <span data-testid="user-drawer-freshness">
          freshness {profile.freshnessAt}
        </span>
      </div>

      <table className="ac-pa-user-drawer__table" data-testid="user-drawer-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>Visibility</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          {profile.fields.map((field) => (
            <tr
              key={field.name}
              data-testid={`user-drawer-row-${field.name}`}
            >
              <td
                className="ac-pa-user-drawer__field-name"
                data-testid={`user-drawer-field-name-${field.name}`}
              >
                {FIELD_LABEL[field.name] ?? field.name}
              </td>
              <td
                className={`ac-pa-user-drawer__visibility ac-pa-user-drawer__visibility--${field.visibility}`}
                data-testid={`user-drawer-visibility-${field.name}`}
                title={`visibility = ${visibilityLabel(field.visibility)}`}
              >
                <span aria-hidden="true">
                  {visibilityGlyph(field.visibility)}
                </span>{' '}
                {visibilityLabel(field.visibility)}
              </td>
              <td
                className="ac-pa-user-drawer__value"
                data-testid={`user-drawer-value-${field.name}`}
              >
                {field.visibility === 'hidden'
                  ? '—'
                  : field.value ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default UserDetailDrawer