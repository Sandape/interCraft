/**
 * BadcaseList — REQ-044 US4 / REQ-061 US10 production list.
 *
 * Renders either legacy seed Badcase rows or operational summaries
 * from `/api/v1/admin-console/ai/badcases`.
 */
import type { Badcase, BadcasePrivacyClass } from '@/types/admin-incidents'
import type { OperationalBadcaseSummary } from '@/admin/api/badcases-production'

export type BadcaseListItem =
  | { kind: 'legacy'; value: Badcase }
  | { kind: 'operational'; value: OperationalBadcaseSummary }

interface BadcaseListProps {
  items: BadcaseListItem[]
  onOpen: (item: BadcaseListItem) => void
  filters?: {
    status?: string
    severity?: string
    sla_status?: string
  }
  unavailable?: boolean
  dataQuality?: {
    fresh_at?: string
    unknown_count?: number
    seed_or_mock_count?: number
  } | null
}

const PRIVACY_GLYPH: Record<string, string> = {
  public: '◌',
  internal: '◐',
  restricted: '⛔',
  metadata: '◌',
  redacted: '◐',
}

function formatTime(ts: string | null | undefined): string {
  if (!ts || ts === 'unknown') return 'stale'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function itemId(item: BadcaseListItem): string {
  return item.kind === 'legacy' ? item.value.id : item.value.badcase_id
}

function itemStatus(item: BadcaseListItem): string {
  return item.kind === 'legacy' ? item.value.status : item.value.status
}

function matchesFilters(
  item: BadcaseListItem,
  filters?: BadcaseListProps['filters'],
): boolean {
  if (!filters) return true
  if (filters.status && filters.status !== 'all') {
    if (itemStatus(item) !== filters.status) return false
  }
  if (filters.severity && filters.severity !== 'all' && item.kind === 'operational') {
    if (item.value.severity !== filters.severity) return false
  }
  if (filters.sla_status && filters.sla_status !== 'all' && item.kind === 'operational') {
    if (item.value.sla_status !== filters.sla_status) return false
  }
  return true
}

export function BadcaseList({
  items,
  onOpen,
  filters,
  unavailable,
  dataQuality,
}: BadcaseListProps) {
  if (unavailable) {
    return (
      <div data-testid="badcase-list-unavailable" className="bc-list bc-list--unavailable">
        Bad Case 数据不可用。请稍后重试，勿使用演示数据。
        {dataQuality?.fresh_at ? (
          <div data-testid="badcase-fresh-at">上次成功：{dataQuality.fresh_at}</div>
        ) : null}
      </div>
    )
  }

  const visible = items.filter((i) => matchesFilters(i, filters))

  return (
    <div>
      {dataQuality ? (
        <div className="bc-list__dq" data-testid="badcase-data-quality">
          <span data-testid="dq-unknown-count">unknown={dataQuality.unknown_count ?? 0}</span>
          <span data-testid="dq-seed-count">seed={dataQuality.seed_or_mock_count ?? 0}</span>
        </div>
      ) : null}
      <ul className="bc-list" data-testid="badcase-list">
        {visible.map((item) => {
          const id = itemId(item)
          if (item.kind === 'legacy') {
            const bc = item.value
            const privacy = bc.privacyClass as BadcasePrivacyClass
            return (
              <li
                key={id}
                className={`bc-list__item bc-list__item--${bc.status}`}
                data-testid={`badcase-card-${id}`}
                data-badcase-id={id}
                data-badcase-status={bc.status}
              >
                <button type="button" className="bc-list__button" onClick={() => onOpen(item)}>
                  <div className="bc-list__left">
                    <span className="bc-list__eval-verdict" data-testid="eval-verdict">
                      {bc.evalVerdict}
                    </span>
                    <span
                      className={`bc-list__privacy bc-list__privacy--${privacy}`}
                      data-testid="privacy-class"
                      data-privacy-class={privacy}
                    >
                      <span aria-hidden="true">{PRIVACY_GLYPH[privacy] ?? '◌'}</span>
                    </span>
                  </div>
                  <div className="bc-list__body">
                    <div className="bc-list__title-row">
                      <span className="bc-list__title">{bc.classification}</span>
                      <span className="bc-list__id">{bc.id}</span>
                    </div>
                    <div className="bc-list__meta">
                      <span className="bc-list__owner">{bc.owner}</span>
                      <span className="bc-list__dot">·</span>
                      <span className="bc-list__first-seen">
                        first seen {formatTime(bc.firstSeenAt)}
                      </span>
                    </div>
                  </div>
                  <div className="bc-list__right">
                    <span className="bc-list__next">Detail →</span>
                  </div>
                </button>
              </li>
            )
          }

          const bc = item.value
          return (
            <li
              key={id}
              className={`bc-list__item bc-list__item--${bc.status}`}
              data-testid={`badcase-card-${id}`}
              data-badcase-id={id}
              data-badcase-status={bc.status}
              data-severity={bc.severity}
              data-sla-status={bc.sla_status}
              data-point-treatment={bc.point_treatment_status}
            >
              <button type="button" className="bc-list__button" onClick={() => onOpen(item)}>
                <div className="bc-list__left">
                  <span className="bc-list__eval-verdict" data-testid="eval-verdict">
                    {bc.severity}
                  </span>
                  <span
                    className={`bc-list__privacy bc-list__privacy--${bc.privacy_class}`}
                    data-testid="privacy-class"
                    data-privacy-class={bc.privacy_class}
                  >
                    <span aria-hidden="true">{PRIVACY_GLYPH[bc.privacy_class] ?? '◌'}</span>
                  </span>
                </div>
                <div className="bc-list__body">
                  <div className="bc-list__title-row">
                    <span className="bc-list__title">{bc.category}</span>
                    <span className="bc-list__id">{bc.badcase_id}</span>
                  </div>
                  <div className="bc-list__meta">
                    <span className="bc-list__owner">{bc.owner ?? 'unassigned'}</span>
                    <span className="bc-list__dot">·</span>
                    <span data-testid="sla-status">{bc.sla_status}</span>
                    <span className="bc-list__dot">·</span>
                    <span className="bc-list__first-seen">
                      first seen {formatTime(bc.first_seen_at)}
                    </span>
                  </div>
                </div>
                <div className="bc-list__right">
                  <span className="bc-list__next">Detail →</span>
                </div>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default BadcaseList
