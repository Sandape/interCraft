/**
 * IncidentsBadcases — REQ-044 US4 / REQ-061 US10.
 *
 * Badcases tab prefers the canonical production facade
 * (`/api/v1/admin-console/ai/badcases`). On failure it shows unavailable
 * (never seed/demo fallback for production facts).
 */
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  useIncidents,
  useProductionBadcases,
} from '@/admin/hooks/queries/useIncidents'
import type {
  EvidenceLink,
  Incident,
  IncidentFilters,
} from '@/types/admin-incidents'
import { IncidentFilterBar } from '@/admin/components/incidents/IncidentFilterBar'
import { IncidentCard } from '@/admin/components/incidents/IncidentCard'
import { IncidentDrawer } from '@/admin/components/incidents/IncidentDrawer'
import {
  BadcaseList,
  type BadcaseListItem,
} from '@/admin/components/incidents/BadcaseList'
import { BadcaseDrawer } from '@/admin/components/incidents/BadcaseDrawer'

type WorkspaceTab = 'incidents' | 'badcases'

const DEFAULT_FILTERS: IncidentFilters = {
  severity: 'all',
  status: 'all',
  owner: 'all',
  featureArea: 'all',
  journey: 'all',
  dateRange: 'all',
  trend: 'all',
}

type BadcaseUiFilters = {
  status: string
  severity: string
  sla_status: string
}

const DEFAULT_BC_FILTERS: BadcaseUiFilters = {
  status: 'all',
  severity: 'all',
  sla_status: 'all',
}

export function IncidentsBadcases() {
  const [tab, setTab] = useState<WorkspaceTab>('incidents')
  const [filters, setFilters] = useState<IncidentFilters>(DEFAULT_FILTERS)
  const [bcFilters, setBcFilters] = useState<BadcaseUiFilters>(DEFAULT_BC_FILTERS)
  const [openIncident, setOpenIncident] = useState<Incident | null>(null)
  const [openBadcase, setOpenBadcase] = useState<BadcaseListItem | null>(null)
  const [searchParams] = useSearchParams()

  const incidentsQuery = useIncidents()
  const productionQuery = useProductionBadcases({
    status: bcFilters.status === 'all' ? undefined : bcFilters.status,
    severity: bcFilters.severity === 'all' ? undefined : bcFilters.severity,
    sla_status: bcFilters.sla_status === 'all' ? undefined : bcFilters.sla_status,
  })

  useEffect(() => {
    const id = searchParams.get('id')
    if (!id || !incidentsQuery.data) return
    const target = incidentsQuery.data.incidents.find((i) => i.id === id)
    if (target) setOpenIncident(target)
  }, [searchParams, incidentsQuery.data])

  const allIncidents = incidentsQuery.data?.incidents ?? []

  const owners = useMemo(
    () => Array.from(new Set(allIncidents.map((i) => i.owner))).sort(),
    [allIncidents],
  )
  const featureAreas = useMemo(
    () =>
      Array.from(new Set(allIncidents.map((i) => i.affectedFeatureArea))).sort(),
    [allIncidents],
  )
  const journeys = useMemo(
    () =>
      Array.from(new Set(allIncidents.map((i) => i.affectedJourneyStep))).sort(),
    [allIncidents],
  )

  const filteredIncidents = useMemo(() => {
    return allIncidents.filter((inc) => {
      if (filters.severity !== 'all' && inc.severity !== filters.severity) return false
      if (filters.status !== 'all' && inc.status !== filters.status) return false
      if (filters.owner !== 'all' && inc.owner !== filters.owner) return false
      if (
        filters.featureArea !== 'all' &&
        inc.affectedFeatureArea !== filters.featureArea
      ) {
        return false
      }
      if (
        filters.journey !== 'all' &&
        inc.affectedJourneyStep !== filters.journey
      ) {
        return false
      }
      if (filters.trend !== 'all' && inc.trend !== filters.trend) return false
      return true
    })
  }, [allIncidents, filters])

  useEffect(() => {
    const handler = (event: Event) => {
      const ce = event as CustomEvent<EvidenceLink>
      const link = ce.detail
      if (!link) return
      console.info('[incidents-badcases] open evidence', link.type, link.href)
    }
    window.addEventListener('ic:open-evidence', handler)
    return () => window.removeEventListener('ic:open-evidence', handler)
  }, [])

  const incidentsTotal = incidentsQuery.data?.total ?? 0
  const incidentsConfirmed = incidentsQuery.data?.confirmedCount ?? 0
  const incidentsCandidate = incidentsQuery.data?.candidateCount ?? 0

  const productionItems: BadcaseListItem[] = (productionQuery.data?.items ?? []).map(
    (value) => ({ kind: 'operational' as const, value }),
  )
  const badcasesTotal = productionItems.length
  const badcasesOpen = productionItems.filter(
    (i) => i.kind === 'operational' && !['CLOSED', 'REJECTED', 'MERGED'].includes(i.value.status),
  ).length
  const productionUnavailable = productionQuery.isError
  const dq = productionQuery.data?.data_quality ?? null

  return (
    <div
      className="ac-page"
      data-testid="incidents-badcases"
      data-workspace-tab={tab}
    >
      <div className="ac-page__header">
        <h1 className="ac-page__title">事件与差例</h1>
        <span className="ac-page__hint">运营分诊 · 影响优先分组</span>
      </div>

      <div className="ib-shell">
        <nav className="ib-tabs" role="tablist" aria-label="Workspace tabs">
          <button
            type="button"
            role="tab"
            className={`ib-tab ${tab === 'incidents' ? 'is-active' : ''}`}
            data-testid="workspace-tab-incidents"
            aria-selected={tab === 'incidents'}
            onClick={() => setTab('incidents')}
          >
            事件
            <span className="ib-tab__count" data-testid="workspace-tab-incidents-count">
              {incidentsTotal}
            </span>
          </button>
          <button
            type="button"
            role="tab"
            className={`ib-tab ${tab === 'badcases' ? 'is-active' : ''}`}
            data-testid="workspace-tab-badcases"
            aria-selected={tab === 'badcases'}
            onClick={() => setTab('badcases')}
          >
            差例
            <span className="ib-tab__count" data-testid="workspace-tab-badcases-count">
              {badcasesTotal}
            </span>
          </button>
        </nav>

        <section className="ib-stats" data-testid="incidents-badcases-stats">
          <div className="ib-stat" data-testid="stat-confirmed">
            <span className="ib-stat__label">已确认事件</span>
            <span className="ib-stat__value">{incidentsConfirmed}</span>
          </div>
          <div className="ib-stat" data-testid="stat-candidate">
            <span className="ib-stat__label">候选事件（低置信度）</span>
            <span className="ib-stat__value">{incidentsCandidate}</span>
          </div>
          <div className="ib-stat" data-testid="stat-badcases-open">
            <span className="ib-stat__label">未关闭差例</span>
            <span className="ib-stat__value">{badcasesOpen}</span>
          </div>
          <div className="ib-stat" data-testid="stat-badcases-total">
            <span className="ib-stat__label">差例总数</span>
            <span className="ib-stat__value">{badcasesTotal}</span>
          </div>
        </section>

        {tab === 'incidents' ? (
          <section className="ib-incidents" data-testid="incidents-section">
            <IncidentFilterBar
              filters={filters}
              onChange={setFilters}
              owners={owners}
              featureAreas={featureAreas}
              journeys={journeys}
            />
            {incidentsQuery.isLoading ? (
              <p className="ib-loading" data-testid="incidents-loading">
                加载事件…
              </p>
            ) : incidentsQuery.isError ? (
              <div className="ac-error-banner" data-testid="incidents-error">
                加载事件失败。
              </div>
            ) : (
              <div className="ib-incidents__list" data-testid="incidents-list">
                {filteredIncidents.length === 0 ? (
                  <p className="ib-incidents__empty" data-testid="incidents-empty">
                    无事件匹配当前筛选条件。
                  </p>
                ) : (
                  filteredIncidents.map((inc) => (
                    <IncidentCard
                      key={inc.id}
                      incident={inc}
                      onOpen={setOpenIncident}
                    />
                  ))
                )}
              </div>
            )}
          </section>
        ) : (
          <section className="ib-badcases" data-testid="badcases-section">
            <div className="ib-badcase-filters" data-testid="badcase-filter-bar">
              <label>
                状态
                <select
                  data-testid="badcase-filter-status"
                  value={bcFilters.status}
                  onChange={(e) =>
                    setBcFilters((f) => ({ ...f, status: e.target.value }))
                  }
                >
                  <option value="all">全部</option>
                  <option value="OPEN">OPEN</option>
                  <option value="TRIAGED">TRIAGED</option>
                  <option value="IN_PROGRESS">IN_PROGRESS</option>
                  <option value="AWAITING_VALIDATION">AWAITING_VALIDATION</option>
                  <option value="CLOSED">CLOSED</option>
                  <option value="REJECTED">REJECTED</option>
                  <option value="MERGED">MERGED</option>
                </select>
              </label>
              <label>
                严重度
                <select
                  data-testid="badcase-filter-severity"
                  value={bcFilters.severity}
                  onChange={(e) =>
                    setBcFilters((f) => ({ ...f, severity: e.target.value }))
                  }
                >
                  <option value="all">全部</option>
                  <option value="P0">P0</option>
                  <option value="P1">P1</option>
                  <option value="P2">P2</option>
                  <option value="P3">P3</option>
                </select>
              </label>
              <label>
                SLA
                <select
                  data-testid="badcase-filter-sla"
                  value={bcFilters.sla_status}
                  onChange={(e) =>
                    setBcFilters((f) => ({ ...f, sla_status: e.target.value }))
                  }
                >
                  <option value="all">全部</option>
                  <option value="within_sla">within_sla</option>
                  <option value="at_risk">at_risk</option>
                  <option value="breached">breached</option>
                </select>
              </label>
            </div>
            {productionQuery.isLoading ? (
              <p className="ib-loading" data-testid="badcases-loading">
                加载差例…
              </p>
            ) : (
              <BadcaseList
                items={productionItems}
                onOpen={setOpenBadcase}
                filters={bcFilters}
                unavailable={productionUnavailable}
                dataQuality={dq}
              />
            )}
          </section>
        )}
      </div>

      <IncidentDrawer
        incident={openIncident}
        onClose={() => setOpenIncident(null)}
        canChange
        canComment
      />
      <BadcaseDrawer
        item={openBadcase}
        onClose={() => setOpenBadcase(null)}
        canEscalate
        canManage
      />
    </div>
  )
}

export default IncidentsBadcases
