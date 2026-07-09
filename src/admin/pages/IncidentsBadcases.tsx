/**
 * IncidentsBadcases — REQ-044 US4 / FR-021~FR-023 业务层.
 *
 * Operations-led workspace for incident triage + badcase review.
 * Layout:
 *
 *   - Header with 3 tabs: Incidents | Badcases
 *   - Workspace-level stats strip
 *   - Tab body:
 *       Incidents: filter bar + list + drawer
 *       Badcases:  list + drawer
 *   - Per-tab drawer (incident or badcase)
 *
 * Cross-workspace drilldown contract (SC-007 3-min drilldown) is
 * satisfied by the Evidence tab in the incident drawer: each link
 * dispatches an `ic:open-evidence` CustomEvent that the page-level
 * listener can map to a route navigation.
 */
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  useIncidents,
  useBadcases,
} from '@/admin/hooks/queries/useIncidents'
import type {
  Badcase,
  EvidenceLink,
  Incident,
  IncidentFilters,
} from '@/types/admin-incidents'
import { IncidentFilterBar } from '@/admin/components/incidents/IncidentFilterBar'
import { IncidentCard } from '@/admin/components/incidents/IncidentCard'
import { IncidentDrawer } from '@/admin/components/incidents/IncidentDrawer'
import { BadcaseList } from '@/admin/components/incidents/BadcaseList'
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

export function IncidentsBadcases() {
  const [tab, setTab] = useState<WorkspaceTab>('incidents')
  const [filters, setFilters] = useState<IncidentFilters>(DEFAULT_FILTERS)
  const [openIncident, setOpenIncident] = useState<Incident | null>(null)
  const [openBadcase, setOpenBadcase] = useState<Badcase | null>(null)
  const [searchParams] = useSearchParams()

  const incidentsQuery = useIncidents()
  const badcasesQuery = useBadcases()

  // Optional ?id=<incident_id> deep-link from the command-center.
  useEffect(() => {
    const id = searchParams.get('id')
    if (!id || !incidentsQuery.data) return
    const target = incidentsQuery.data.incidents.find((i) => i.id === id)
    if (target) setOpenIncident(target)
  }, [searchParams, incidentsQuery.data])

  const allIncidents = incidentsQuery.data?.incidents ?? []
  const allBadcases = badcasesQuery.data?.badcases ?? []

  // Distinct owner / feature_area / journey values for the filter bar.
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
      if (filters.severity !== 'all' && inc.severity !== filters.severity) {
        return false
      }
      if (filters.status !== 'all' && inc.status !== filters.status) {
        return false
      }
      if (filters.owner !== 'all' && inc.owner !== filters.owner) {
        return false
      }
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
      if (filters.trend !== 'all' && inc.trend !== filters.trend) {
        return false
      }
      return true
    })
  }, [allIncidents, filters])

  // Cross-workspace drilldown handler (SC-007 3-min drilldown).
  useEffect(() => {
    const handler = (event: Event) => {
      const ce = event as CustomEvent<EvidenceLink>
      const link = ce.detail
      if (!link) return
      // [CROSS-TEAM-DEBT] Phase 2 batch 4 will replace this stub with
      // a real navigate(link.href) call. For US4 we surface the link
      // type so Playwright can verify the 8-type coverage.
      console.info('[incidents-badcases] open evidence', link.type, link.href)
    }
    window.addEventListener('ic:open-evidence', handler)
    return () => window.removeEventListener('ic:open-evidence', handler)
  }, [])

  const incidentsTotal = incidentsQuery.data?.total ?? 0
  const incidentsConfirmed = incidentsQuery.data?.confirmedCount ?? 0
  const incidentsCandidate = incidentsQuery.data?.candidateCount ?? 0
  const badcasesTotal = badcasesQuery.data?.total ?? 0
  const badcasesOpen = badcasesQuery.data?.openCount ?? 0
  const badcasesEscalated = badcasesQuery.data?.escalatedCount ?? 0

  return (
    <div
      className="ac-page"
      data-testid="incidents-badcases"
      data-workspace-tab={tab}
    >
      <div className="ac-page__header">
        <h1 className="ac-page__title">事件与差例</h1>
        <span className="ac-page__hint">
          运营分诊 · 影响优先分组
        </span>
      </div>

      <div className="ib-shell">
        <nav
          className="ib-tabs"
          role="tablist"
          aria-label="Workspace tabs"
        >
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

        <section
          className="ib-stats"
          data-testid="incidents-badcases-stats"
        >
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
          <div className="ib-stat" data-testid="stat-badcases-escalated">
            <span className="ib-stat__label">已升级差例</span>
            <span className="ib-stat__value">{badcasesEscalated}</span>
          </div>
        </section>

        {tab === 'incidents' ? (
          <section
            className="ib-incidents"
            data-testid="incidents-section"
          >
            <IncidentFilterBar
              filters={filters}
              onChange={setFilters}
              owners={owners}
              featureAreas={featureAreas}
              journeys={journeys}
            />
            {incidentsQuery.isLoading ? (
              <p
                className="ib-loading"
                data-testid="incidents-loading"
              >
                加载事件…
              </p>
            ) : incidentsQuery.isError ? (
              <div className="ac-error-banner" data-testid="incidents-error">
                加载事件失败。
              </div>
            ) : (
              <div
                className="ib-incidents__list"
                data-testid="incidents-list"
              >
                {filteredIncidents.length === 0 ? (
                  <p
                    className="ib-incidents__empty"
                    data-testid="incidents-empty"
                  >
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
            {badcasesQuery.isLoading ? (
              <p
                className="ib-loading"
                data-testid="badcases-loading"
              >
                加载差例…
              </p>
            ) : badcasesQuery.isError ? (
              <div className="ac-error-banner" data-testid="badcases-error">
                加载差例失败。
              </div>
            ) : (
              <BadcaseList
                badcases={allBadcases}
                onOpen={setOpenBadcase}
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
        badcase={openBadcase}
        onClose={() => setOpenBadcase(null)}
        canEscalate
      />
    </div>
  )
}

export default IncidentsBadcases
