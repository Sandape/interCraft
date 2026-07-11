/**
 * BadcaseDrawer — REQ-044 US4 + REQ-061 US10 production detail.
 *
 * Tabs: overview | impacts | actions | privacy
 * Typed commands POST to canonical facade with Idempotency-Key.
 */
import { useEffect, useState } from 'react'
import type { Badcase } from '@/types/admin-incidents'
import {
  productionBadcasesApi,
  type BadcaseImpact,
  type ImpactConfidence,
  type OperationalBadcaseSummary,
} from '@/admin/api/badcases-production'
import type { BadcaseListItem } from './BadcaseList'
import { useEscalateBadcase } from '@/admin/hooks/queries/useIncidents'

type Tab = 'overview' | 'impacts' | 'actions' | 'privacy'

interface BadcaseDrawerProps {
  item: BadcaseListItem | null
  onClose: () => void
  canEscalate: boolean
  canManage?: boolean
}

const CONFIDENCES: ImpactConfidence[] = [
  'confirmed',
  'possible',
  'excluded',
  'unknown',
]

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

export function BadcaseDrawer({
  item,
  onClose,
  canEscalate,
  canManage = false,
}: BadcaseDrawerProps) {
  const [tab, setTab] = useState<Tab>('overview')
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null)
  const [impacts, setImpacts] = useState<BadcaseImpact[]>([])
  const [impactFilter, setImpactFilter] = useState<ImpactConfidence | 'all'>('all')
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const escalate = useEscalateBadcase()

  const isOperational = item?.kind === 'operational'
  const legacy = item?.kind === 'legacy' ? item.value : null
  const summary = item?.kind === 'operational' ? item.value : null
  const badcaseId = legacy?.id ?? summary?.badcase_id ?? null

  useEffect(() => {
    if (!isOperational || !badcaseId) {
      setDetail(null)
      setImpacts([])
      return
    }
    let cancelled = false
    void (async () => {
      try {
        const [d, i] = await Promise.all([
          productionBadcasesApi.get(badcaseId),
          productionBadcasesApi.impacts(badcaseId),
        ])
        if (!cancelled) {
          setDetail(d)
          setImpacts(i.items)
        }
      } catch {
        if (!cancelled) {
          setDetail(null)
          setImpacts([])
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [isOperational, badcaseId])

  if (!item || !badcaseId) return null

  const onEscalate = async () => {
    await escalate.mutateAsync(badcaseId)
  }

  const runAction = async (command: Record<string, unknown>) => {
    if (!summary || !canManage) return
    setBusy(true)
    setActionError(null)
    try {
      await productionBadcasesApi.action(
        badcaseId,
        {
          ...command,
          action_type: String(command.action_type),
          expected_version: summary.version,
          reason: String(command.reason ?? 'operator action'),
        },
        `ui-${badcaseId}-${Date.now()}`,
      )
      const refreshed = await productionBadcasesApi.get(badcaseId)
      setDetail(refreshed)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'action failed'
      setActionError(message)
    } finally {
      setBusy(false)
    }
  }

  const filteredImpacts =
    impactFilter === 'all'
      ? impacts
      : impacts.filter((i) => i.confidence === impactFilter)

  const title =
    legacy?.classification ?? summary?.category ?? badcaseId

  return (
    <aside
      className="bc-drawer"
      data-testid="badcase-drawer"
      data-badcase-id={badcaseId}
      role="dialog"
      aria-label={`Badcase ${badcaseId}`}
    >
      <header className="bc-drawer__header">
        <div className="bc-drawer__title-row">
          <span className="bc-drawer__id">{badcaseId}</span>
          {summary ? (
            <span data-testid="drawer-severity">{summary.severity}</span>
          ) : null}
          <button
            type="button"
            className="bc-drawer__close"
            data-testid="badcase-drawer-close"
            onClick={onClose}
            aria-label="Close drawer"
          >
            ×
          </button>
        </div>
        <h2 className="bc-drawer__title">{title}</h2>
        <nav className="bc-drawer__tabs" role="tablist" aria-label="Badcase detail tabs">
          {(
            [
              ['overview', '概览'],
              ['impacts', '影响范围'],
              ['actions', '审核动作'],
              ['privacy', '隐私'],
            ] as Array<[Tab, string]>
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              data-testid={`badcase-tab-${id}`}
              className={tab === id ? 'bc-drawer__tab bc-drawer__tab--active' : 'bc-drawer__tab'}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </nav>
      </header>

      <div className="bc-drawer__body">
        {tab === 'overview' ? (
          <section data-testid="badcase-tab-panel-overview">
            {legacy ? (
              <dl>
                <dt>状态</dt>
                <dd>{legacy.status}</dd>
                <dt>Owner</dt>
                <dd>{legacy.owner}</dd>
                <dt>首次发现</dt>
                <dd>{formatTime(legacy.firstSeenAt)}</dd>
              </dl>
            ) : summary ? (
              <dl>
                <dt>状态</dt>
                <dd data-testid="overview-status">{summary.status}</dd>
                <dt>严重度</dt>
                <dd>{summary.severity}</dd>
                <dt>Owner</dt>
                <dd>{summary.owner ?? '—'}</dd>
                <dt>SLA</dt>
                <dd>{summary.sla_status}</dd>
                <dt>费用处理</dt>
                <dd>{summary.point_treatment_status}</dd>
                <dt>版本</dt>
                <dd data-testid="overview-version">{summary.version}</dd>
                <dt>完整度</dt>
                <dd>{summary.data_completeness}</dd>
                {detail && (detail as { user_visible_status?: string }).user_visible_status ? (
                  <>
                    <dt>用户可见状态</dt>
                    <dd>{String((detail as { user_visible_status?: string }).user_visible_status)}</dd>
                  </>
                ) : null}
              </dl>
            ) : null}
          </section>
        ) : null}

        {tab === 'impacts' ? (
          <section data-testid="badcase-tab-panel-impacts">
            <div className="bc-drawer__impact-filters" data-testid="impact-confidence-filters">
              <button
                type="button"
                data-testid="impact-filter-all"
                onClick={() => setImpactFilter('all')}
              >
                全部
              </button>
              {CONFIDENCES.map((c) => (
                <button
                  key={c}
                  type="button"
                  data-testid={`impact-filter-${c}`}
                  aria-pressed={impactFilter === c}
                  onClick={() => setImpactFilter(c)}
                >
                  {c}
                </button>
              ))}
            </div>
            <ul data-testid="impact-list">
              {filteredImpacts.map((impact) => (
                <li
                  key={impact.impact_id}
                  data-testid={`impact-${impact.impact_id}`}
                  data-confidence={impact.confidence}
                >
                  {impact.impact_kind}:{impact.subject_ref} ({impact.confidence})
                </li>
              ))}
            </ul>
            {filteredImpacts.length === 0 ? (
              <p data-testid="impact-empty-unknown">无匹配影响（未知不得显示为 0 任务）</p>
            ) : null}
          </section>
        ) : null}

        {tab === 'actions' ? (
          <section data-testid="badcase-tab-panel-actions">
            {actionError ? (
              <div data-testid="action-error" role="alert">
                {actionError}
              </div>
            ) : null}
            {canManage && summary ? (
              <div className="bc-drawer__actions">
                <button
                  type="button"
                  data-testid="action-add-note"
                  disabled={busy}
                  onClick={() =>
                    void runAction({
                      action_type: 'ADD_NOTE',
                      note: 'operator note',
                      reason: 'drawer note',
                    })
                  }
                >
                  加注
                </button>
                <button
                  type="button"
                  data-testid="action-close"
                  disabled={busy}
                  onClick={() =>
                    void runAction({
                      action_type: 'CLOSE',
                      reason: 'attempt close',
                      closure_reason: 'fixed',
                      // Intentionally incomplete — UI must surface closure gate
                    })
                  }
                >
                  尝试关闭
                </button>
              </div>
            ) : (
              <p data-testid="actions-read-only">只读或无质量管理权限</p>
            )}
          </section>
        ) : null}

        {tab === 'privacy' ? (
          <section data-testid="badcase-tab-panel-privacy">
            <p data-privacy-class={legacy?.privacyClass ?? summary?.privacy_class}>
              隐私等级：{legacy?.privacyClass ?? summary?.privacy_class}
            </p>
            <p>完整内容 reveal 需要独立授权、理由与审计，合并不会扩大权限。</p>
          </section>
        ) : null}
      </div>

      <footer className="bc-drawer__footer">
        {canEscalate && legacy ? (
          <button
            type="button"
            data-testid="badcase-escalate"
            onClick={() => void onEscalate()}
          >
            升级为 Incident
          </button>
        ) : null}
      </footer>
    </aside>
  )
}

/** @deprecated Prefer BadcaseDrawer with BadcaseListItem */
export function BadcaseDrawerLegacy({
  badcase,
  onClose,
  canEscalate,
}: {
  badcase: Badcase | null
  onClose: () => void
  canEscalate: boolean
}) {
  if (!badcase) return null
  return (
    <BadcaseDrawer
      item={{ kind: 'legacy', value: badcase }}
      onClose={onClose}
      canEscalate={canEscalate}
    />
  )
}

export type { OperationalBadcaseSummary }
export default BadcaseDrawer
