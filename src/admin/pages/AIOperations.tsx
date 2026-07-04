/**
 * AIOperations — REQ-044 US3 / FR-016~FR-020.
 *
 * AI Operations workspace:
 *
 *   - 4 KPI tiles (FR-016)
 *   - Volume-by-Feature bar chart (FR-016/AC-16.2)
 *   - Failure categories pie/legend (FR-016/AC-16.3)
 *   - Latency bands p50/p95/p99 table (FR-016/AC-16.4)
 *   - Token usage stacked bar (FR-016/AC-16.5)
 *   - Cost summary card with stale flag (FR-016/AC-16.6 + EC-3)
 *   - Version selector (4 dimensions, FR-017/AC-17.1 + EC-2) and
 *     feature_area filter (FR-017/AC-17.2)
 *   - "Comparing X vs Y" label surfaced when a selection is made
 *     (FR-017/AC-17.4 + FR-017/AC-17.5)
 *   - Cost-quality alert banner (FR-019/AC-19.1/19.2)
 *   - Quality issue drawer (FR-018/AC-18.1/18.2); alert click jumps
 *     into the drawer (FR-019/AC-19.3)
 *   - Eval + badcase summary card (FR-020/AC-20.1/20.2/20.3)
 *   - Cohort picker shared with Product Analytics (FR-017/AC-17.3)
 *
 * Edge Cases handled:
 *
 *   - EC-1: zero AI tasks → "0 AI tasks" banner + freshness warning
 *   - EC-2: version unknown → explicit warning under each version
 *     dimension (NOT silent fold into baseline)
 *   - EC-3: cost reconciliation stale → "cost estimate outdated"
 *     warning above the cost card
 *
 * [CROSS-TEAM-DEBT] Phase 2 batch 3 will replace the seed-driven
 * panels with real AIInvocationRecord + REQ-026 eval + REQ-033
 * badcases aggregations.
 */
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useCostQualityFlag,
  useCostSummary,
  useEvalBadcaseSummary,
  useFailureCategories,
  useKpis,
  useLatencyBands,
  useQualityIssues,
  useTokenUsage,
  useVersionSelector,
  useVolumeByFeature,
} from '@/admin/hooks/queries/useAIOperations'
import { useCohorts } from '@/admin/hooks/queries/useProductAnalytics'
import { KPITiles } from '@/admin/components/ai-operations/KPITiles'
import { VolumeByFeatureChart } from '@/admin/components/ai-operations/VolumeByFeatureChart'
import { FailureCategoriesPie } from '@/admin/components/ai-operations/FailureCategoriesPie'
import { LatencyBandsChart } from '@/admin/components/ai-operations/LatencyBandsChart'
import { TokenUsageChart } from '@/admin/components/ai-operations/TokenUsageChart'
import { CostSummaryCard } from '@/admin/components/ai-operations/CostSummaryCard'
import { VersionSelector } from '@/admin/components/ai-operations/VersionSelector'
import { QualityIssueDrawer } from '@/admin/components/ai-operations/QualityIssueDrawer'
import { CostQualityAlert } from '@/admin/components/ai-operations/CostQualityAlert'
import { EvalBadcaseSummaryCard } from '@/admin/components/ai-operations/EvalBadcaseSummary'
import { CohortPicker } from '@/admin/components/product-analytics/CohortPicker'
import type { AIQualityIssue } from '@/types/admin-ai-operations'

export function AIOperations() {
  const navigate = useNavigate()
  const [selectedCohortId, setSelectedCohortId] = useState<string | null>(null)
  const [openIssue, setOpenIssue] = useState<AIQualityIssue | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const kpisQuery = useKpis()
  const volumeQuery = useVolumeByFeature()
  const failureQuery = useFailureCategories()
  const latencyQuery = useLatencyBands()
  const tokenQuery = useTokenUsage()
  const costSummaryQuery = useCostSummary()
  const versionSelectorQuery = useVersionSelector()
  const qualityIssuesQuery = useQualityIssues()
  const costQualityFlagQuery = useCostQualityFlag()
  const evalBadcaseSummaryQuery = useEvalBadcaseSummary()
  const cohortsQuery = useCohorts()

  // AC-17.4 + AC-17.5 — refresh / comparison
  const [versionSelection, setVersionSelection] = useState<
    Record<string, string>
  >({})
  const [featureAreaFilter, setFeatureAreaFilter] = useState<string[]>([])

  const handleVersionChange = (
    selection: Record<string, string>,
    areas: string[],
  ) => {
    setVersionSelection(selection)
    setFeatureAreaFilter(areas)
  }

  // AC-19.3 — alert opens the drawer
  const handleAlertOpenIssue = (issue: AIQualityIssue) => {
    setOpenIssue(issue)
    setDrawerOpen(true)
  }

  // AC-20.3 — "View in Logs" jumps to logs-and-traces (US5 placeholder)
  const handleViewInLogs = () => {
    navigate(
      `/admin-console/logs-and-traces${selectedCohortId ? `?cohort=${selectedCohortId}` : ''}`,
    )
  }

  const highestSeverityIssue = useMemo<AIQualityIssue | null>(() => {
    const issues = qualityIssuesQuery.data?.issues ?? []
    return issues[0] ?? null
  }, [qualityIssuesQuery.data])

  const cohortName = useMemo(() => {
    if (!selectedCohortId) return null
    return (
      cohortsQuery.data?.cohorts.find(
        (c: { id: string; name: string }) => c.id === selectedCohortId,
      )?.name ?? null
    )
  }, [cohortsQuery.data, selectedCohortId])

  const versionSelectorData = versionSelectorQuery.data ?? null
  const isComparing =
    Object.values(versionSelection).some(Boolean) || featureAreaFilter.length > 0

  return (
    <div className="ac-page ac-ao-page" data-testid="ai-operations">
      <div className="ac-page__header">
        <h1 className="ac-page__title">AI Operations</h1>
        <span className="ac-page__hint">
          质量 · 成本 · 时延 · 版本 · 评测 · Badcase
        </span>
      </div>

      <div className="ac-ao-page__layout">
        <main className="ac-ao-page__main">
          {/* FR-019: cost-quality banner */}
          {costQualityFlagQuery.data && highestSeverityIssue && (
            <CostQualityAlert
              flag={costQualityFlagQuery.data}
              onOpenQualityIssue={handleAlertOpenIssue}
              fallbackIssue={highestSeverityIssue}
            />
          )}

          {/* FR-016: 4 KPI tiles */}
          {kpisQuery.data && (
            <section
              className="ac-ao-page__kpis"
              data-testid="ai-operations-kpis-section"
            >
              <h2 className="ac-ao-page__section-title">Headline KPIs</h2>
              <KPITiles kpis={kpisQuery.data.kpis} />
            </section>
          )}

          {/* FR-017: version selector */}
          {versionSelectorData && (
            <section
              className="ac-ao-page__version-selector"
              data-testid="ai-operations-version-selector-section"
            >
              <h2 className="ac-ao-page__section-title">Version selector</h2>
              <VersionSelector
                data={versionSelectorData}
                onChange={handleVersionChange}
              />
              {isComparing && (
                <div
                  className="ac-ao-page__compare-banner"
                  data-testid="comparing-banner"
                  role="status"
                >
                  Comparing against baseline ({versionSelectorData.baselineLabel}) —
                  filter applied
                </div>
              )}
            </section>
          )}

          {/* FR-016 volume + failure */}
          <div className="ac-ao-page__row">
            {volumeQuery.data && (
              <section
                className="ac-ao-page__panel"
                data-testid="ai-operations-volume-section"
              >
                <h2 className="ac-ao-page__section-title">
                  Volume by feature area
                </h2>
                <VolumeByFeatureChart
                  rows={volumeQuery.data.rows}
                  versionSelector={versionSelectorData}
                />
              </section>
            )}

            {failureQuery.data && (
              <section
                className="ac-ao-page__panel"
                data-testid="ai-operations-failure-section"
              >
                <h2 className="ac-ao-page__section-title">
                  Failure categories
                </h2>
                <FailureCategoriesPie
                  rows={failureQuery.data.breakdown}
                  versionSelector={versionSelectorData}
                />
              </section>
            )}
          </div>

          {/* FR-016 latency + tokens */}
          <div className="ac-ao-page__row">
            {latencyQuery.data && (
              <section
                className="ac-ao-page__panel"
                data-testid="ai-operations-latency-section"
              >
                <h2 className="ac-ao-page__section-title">Latency bands</h2>
                <LatencyBandsChart
                  entries={latencyQuery.data.entries}
                  versionSelector={versionSelectorData}
                />
              </section>
            )}

            {tokenQuery.data && (
              <section
                className="ac-ao-page__panel"
                data-testid="ai-operations-token-section"
              >
                <h2 className="ac-ao-page__section-title">Token usage</h2>
                <TokenUsageChart
                  rows={tokenQuery.data.rows}
                  versionSelector={versionSelectorData}
                />
              </section>
            )}
          </div>

          {/* FR-016 cost + FR-020 eval/badcase */}
          <div className="ac-ao-page__row">
            {costSummaryQuery.data && (
              <section
                className="ac-ao-page__panel"
                data-testid="ai-operations-cost-section"
              >
                <h2 className="ac-ao-page__section-title">Cost summary</h2>
                <CostSummaryCard summary={costSummaryQuery.data} />
              </section>
            )}

            {evalBadcaseSummaryQuery.data && (
              <section
                className="ac-ao-page__panel"
                data-testid="ai-operations-eval-badcase-section"
              >
                <EvalBadcaseSummaryCard
                  summary={evalBadcaseSummaryQuery.data}
                  onViewInLogs={handleViewInLogs}
                />
              </section>
            )}
          </div>

          {/* FR-018 quality issues list + drawer trigger */}
          {qualityIssuesQuery.data && (
            <section
              className="ac-ao-page__panel"
              data-testid="ai-operations-quality-issues-section"
            >
              <h2 className="ac-ao-page__section-title">AI quality issues</h2>
              <ul className="ac-ao-page__issues-list">
                {qualityIssuesQuery.data.issues.map((issue) => (
                  <li
                    key={issue.issueId}
                    className="ac-ao-page__issue"
                    data-testid={`quality-issue-${issue.issueId}`}
                  >
                    <button
                      type="button"
                      className="ac-ao-page__issue-button"
                      onClick={() => {
                        setOpenIssue(issue)
                        setDrawerOpen(true)
                      }}
                      data-testid={`quality-issue-open-${issue.issueId}`}
                    >
                      <span>{issue.title}</span>
                      <span
                        className={`ac-ao-page__issue-severity ac-ao-page__issue-severity--${issue.severity}`}
                        data-testid={`quality-issue-severity-${issue.issueId}`}
                      >
                        {issue.severity}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </main>

        <aside className="ac-ao-page__sidebar" data-testid="ai-operations-sidebar">
          <h2 className="ac-ao-page__section-title">Cohort</h2>
          {cohortsQuery.isLoading ? (
            <div data-testid="cohort-loading">加载中...</div>
          ) : cohortsQuery.isError ? (
            <div data-testid="cohort-error">加载失败</div>
          ) : cohortsQuery.data ? (
            <CohortPicker
              cohorts={cohortsQuery.data.cohorts}
              selectedCohortId={selectedCohortId}
              onSelect={setSelectedCohortId}
            />
          ) : null}
          {cohortName && (
            <div
              className="ac-ao-page__sidebar-meta"
              data-testid="ai-operations-cohort-tag"
            >
              当前 cohort: <strong>{cohortName}</strong>
            </div>
          )}
        </aside>

        <QualityIssueDrawer
          issue={openIssue}
          onClose={() => setDrawerOpen(false)}
          open={drawerOpen}
        />
      </div>
    </div>
  )
}

export default AIOperations
