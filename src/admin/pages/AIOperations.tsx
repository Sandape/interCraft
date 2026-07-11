/**
 * AIOperations — REQ-044 US3 panels + REQ-061 US9 production surface (T121).
 *
 * Production block: stability / quality / latency / points / costs /
 * unknowns / freshness / budgets / abnormal consumption + cost drilldown.
 * Legacy seed panels remain below for compatibility until T170 cuts them.
 */
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  defaultMetricsFilters,
  useCostQualityFlag,
  useCostSummary,
  useEvalBadcaseSummary,
  useFailureCategories,
  useKpis,
  useLatencyBands,
  useProductionAnomalies,
  useProductionBudgets,
  useProductionMetrics,
  useProductionReconciliations,
  useQualityIssues,
  useTaskCostDrilldown,
  useTokenUsage,
  useVersionSelector,
  useVolumeByFeature,
  type MetricsFilters,
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
import { AICostDrilldown } from '@/admin/components/ai-operations/AICostDrilldown'
import { PointCostTimeline } from '@/admin/components/ai-operations/PointCostTimeline'
import { CohortPicker } from '@/admin/components/product-analytics/CohortPicker'
import type { AIQualityIssue } from '@/types/admin-ai-operations'

function metricNumber(value: unknown, fallback = 'unknown'): string {
  if (value === null || value === undefined) return fallback
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  if (typeof value === 'string' && value.length > 0) return value
  return fallback
}

export function AIOperations() {
  const navigate = useNavigate()
  const [selectedCohortId, setSelectedCohortId] = useState<string | null>(null)
  const [openIssue, setOpenIssue] = useState<AIQualityIssue | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [filters, setFilters] = useState<MetricsFilters>(defaultMetricsFilters)
  const [draftFilters, setDraftFilters] = useState<MetricsFilters>(filters)
  const [drillTaskId, setDrillTaskId] = useState<string | null>(null)
  const [drillOpen, setDrillOpen] = useState(false)

  const metricsQuery = useProductionMetrics(filters)
  const budgetsQuery = useProductionBudgets()
  const reconciliationsQuery = useProductionReconciliations()
  const anomaliesQuery = useProductionAnomalies()
  const drilldownQuery = useTaskCostDrilldown(drillTaskId)

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

  const handleAlertOpenIssue = (issue: AIQualityIssue) => {
    setOpenIssue(issue)
    setDrawerOpen(true)
  }

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

  const metrics = metricsQuery.data
  const dq = metrics?.data_quality

  const applyFilters = () => {
    setFilters({ ...draftFilters })
  }

  const openDrilldown = () => {
    const taskId =
      draftFilters.capability || filters.capability
        ? `task-${(draftFilters.capability || filters.capability || 'demo').replace(/\W+/g, '-')}`
        : '00000000-0000-7000-8000-000000000061'
    setDrillTaskId(taskId)
    setDrillOpen(true)
  }

  return (
    <div className="ac-page ac-ao-page" data-testid="ai-operations">
      <div className="ac-page__header">
        <h1 className="ac-page__title">AI 运营</h1>
        <span className="ac-page__hint">
          真实质量 · 成本 · 时延 · 积分 · 预算 · 异常消耗
        </span>
        <Link
          to="/admin-console/model-policies"
          data-testid="ai-operations-model-policies-link"
          style={{ marginLeft: 12, fontSize: 12 }}
        >
          模型策略
        </Link>
      </div>

      <div className="ac-ao-page__layout">
        <main className="ac-ao-page__main">
          {/* REQ-061 US9 production filters + metrics */}
          <section
            className="ac-ao-page__panel"
            data-testid="ai-operations-production"
          >
            <h2 className="ac-ao-page__section-title">生产联合指标</h2>
            <form
              className="ac-ao-page__filters"
              data-testid="ai-operations-filters"
              onSubmit={(e) => {
                e.preventDefault()
                applyFilters()
              }}
            >
              <label>
                capability
                <input
                  data-testid="filter-capability"
                  value={draftFilters.capability ?? ''}
                  onChange={(e) =>
                    setDraftFilters((f) => ({
                      ...f,
                      capability: e.target.value,
                    }))
                  }
                />
              </label>
              <label>
                service_tier
                <select
                  data-testid="filter-service-tier"
                  value={draftFilters.serviceTier ?? ''}
                  onChange={(e) =>
                    setDraftFilters((f) => ({
                      ...f,
                      serviceTier: e.target.value as MetricsFilters['serviceTier'],
                    }))
                  }
                >
                  <option value="">all</option>
                  <option value="standard">standard</option>
                  <option value="quality">quality</option>
                </select>
              </label>
              <label>
                policy_version
                <input
                  data-testid="filter-policy-version"
                  value={draftFilters.policyVersion ?? ''}
                  onChange={(e) =>
                    setDraftFilters((f) => ({
                      ...f,
                      policyVersion: e.target.value,
                    }))
                  }
                />
              </label>
              <label>
                release_batch
                <input
                  data-testid="filter-release-batch"
                  value={draftFilters.releaseBatch ?? ''}
                  onChange={(e) =>
                    setDraftFilters((f) => ({
                      ...f,
                      releaseBatch: e.target.value,
                    }))
                  }
                />
              </label>
              <button type="submit" data-testid="filter-apply">
                应用筛选
              </button>
              <button
                type="button"
                data-testid="open-cost-drilldown"
                onClick={openDrilldown}
              >
                打开费用下钻
              </button>
            </form>

            {metricsQuery.isLoading && (
              <div data-testid="production-metrics-loading">加载中…</div>
            )}
            {metricsQuery.isError && (
              <div data-testid="production-metrics-error" role="alert">
                生产指标不可用
              </div>
            )}

            {metrics && dq && (
              <>
                <div
                  className="ac-ao-page__dq"
                  data-testid="production-data-quality"
                  data-seed-or-mock={dq.seed_or_mock_count}
                  data-unknown-count={dq.unknown_count}
                >
                  <span>fresh_at={dq.fresh_at}</span>
                  {' · '}
                  <span>coverage={dq.coverage_percent}%</span>
                  {' · '}
                  <span data-testid="production-unknown-count">
                    unknowns={dq.unknown_count}
                  </span>
                  {' · '}
                  <span data-testid="production-seed-count">
                    seed_or_mock={dq.seed_or_mock_count}
                  </span>
                </div>

                <div
                  className="ac-ao-page__row"
                  data-testid="production-metric-tiles"
                >
                  <div data-testid="metric-stability">
                    <h3>稳定性</h3>
                    <p>
                      success_rate=
                      {metricNumber(metrics.stability.success_rate)}
                    </p>
                  </div>
                  <div data-testid="metric-quality">
                    <h3>质量</h3>
                    <p>
                      badcase_rate=
                      {metricNumber(metrics.quality.badcase_rate)}
                    </p>
                  </div>
                  <div data-testid="metric-latency">
                    <h3>时延</h3>
                    <p>
                      p95=
                      {metricNumber(metrics.latency.p95_ms)}
                      ms
                    </p>
                  </div>
                  <div data-testid="metric-points">
                    <h3>积分</h3>
                    <p>
                      settled=
                      {metricNumber(metrics.points.settled_total)}
                    </p>
                  </div>
                  <div data-testid="metric-cost">
                    <h3>成本</h3>
                    <p>
                      rmb=
                      {metricNumber(metrics.cost.rmb_total)}
                    </p>
                  </div>
                  <div data-testid="metric-revenue">
                    <h3>收入（beta=0）</h3>
                    <p data-testid="beta-revenue-amount">
                      {metrics.revenue_rmb.amount} {metrics.revenue_rmb.currency}
                    </p>
                  </div>
                </div>
              </>
            )}
          </section>

          <div className="ac-ao-page__row">
            <section
              className="ac-ao-page__panel"
              data-testid="ai-operations-budgets"
            >
              <h2 className="ac-ao-page__section-title">预算</h2>
              {(budgetsQuery.data?.items ?? []).length === 0 ? (
                <p data-testid="budgets-empty">暂无预算行</p>
              ) : (
                <ul>
                  {(budgetsQuery.data?.items ?? []).map((b) => (
                    <li key={b.budget_id} data-testid={`budget-${b.budget_id}`}>
                      {b.scope_type}/{b.scope_ref} · {b.utilization_percent}% ·
                      level={b.level}
                      {b.warning_reached ? ' · warning' : ''}
                      {b.hard_limit_reached ? ' · hard' : ''}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section
              className="ac-ao-page__panel"
              data-testid="ai-operations-anomalies"
            >
              <h2 className="ac-ao-page__section-title">异常消耗</h2>
              <p data-testid="anomaly-protected-ops">
                受保护操作：
                {(anomaliesQuery.data?.protected_operations ?? []).join(', ') ||
                  'query, cancel, appeal'}
              </p>
              {(anomaliesQuery.data?.items ?? []).length === 0 ? (
                <p data-testid="anomalies-empty">当前无触发异常防护</p>
              ) : (
                <ul>
                  {(anomaliesQuery.data?.items ?? []).map((item, idx) => (
                    <li key={idx} data-testid={`anomaly-${idx}`}>
                      {JSON.stringify(item)}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          <section
            className="ac-ao-page__panel"
            data-testid="ai-operations-reconciliations"
          >
            <h2 className="ac-ao-page__section-title">对账</h2>
            {(reconciliationsQuery.data?.items ?? []).length === 0 ? (
              <p data-testid="reconciliations-empty">暂无对账运行</p>
            ) : (
              <ul>
                {(reconciliationsQuery.data?.items ?? []).map((r, idx) => (
                  <li key={`${r.run_type}-${idx}`}>
                    {r.run_type} · {r.status} · issues={r.issue_count}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {drillOpen && (
            <section
              className="ac-ao-page__panel"
              data-testid="ai-operations-drilldown-panel"
            >
              <h2 className="ac-ao-page__section-title">
                point → milestone → attempt → cost
              </h2>
              <PointCostTimeline
                milestones={
                  (drilldownQuery.data?.milestones ?? []) as Array<{
                    milestone?: string
                    points?: number | null
                    cost_rmb?: string | null
                  }>
                }
                pointSettled={drilldownQuery.data?.point_settled}
              />
              <AICostDrilldown
                open={drillOpen}
                drilldown={drilldownQuery.data ?? null}
                isLoading={drilldownQuery.isLoading}
                errorMessage={
                  drilldownQuery.isError ? '费用下钻不可用' : null
                }
                onClose={() => {
                  setDrillOpen(false)
                  setDrillTaskId(null)
                }}
              />
            </section>
          )}

          {/* Legacy REQ-044 panels */}
          {costQualityFlagQuery.data && highestSeverityIssue && (
            <CostQualityAlert
              flag={costQualityFlagQuery.data}
              onOpenQualityIssue={handleAlertOpenIssue}
              fallbackIssue={highestSeverityIssue}
            />
          )}

          {kpisQuery.data && (
            <section
              className="ac-ao-page__kpis"
              data-testid="ai-operations-kpis-section"
            >
              <h2 className="ac-ao-page__section-title">核心指标（兼容）</h2>
              <KPITiles kpis={kpisQuery.data.kpis} />
            </section>
          )}

          {versionSelectorData && (
            <section
              className="ac-ao-page__version-selector"
              data-testid="ai-operations-version-selector-section"
            >
              <h2 className="ac-ao-page__section-title">版本选择器</h2>
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
                  正在与基线比较 ({versionSelectorData.baselineLabel}) —
                  筛选器已应用
                </div>
              )}
            </section>
          )}

          <div className="ac-ao-page__row">
            {volumeQuery.data && (
              <section
                className="ac-ao-page__panel"
                data-testid="ai-operations-volume-section"
              >
                <h2 className="ac-ao-page__section-title">
                  按功能区域统计调用量
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
                <h2 className="ac-ao-page__section-title">失败分类</h2>
                <FailureCategoriesPie
                  rows={failureQuery.data.breakdown}
                  versionSelector={versionSelectorData}
                />
              </section>
            )}
          </div>

          <div className="ac-ao-page__row">
            {latencyQuery.data && (
              <section
                className="ac-ao-page__panel"
                data-testid="ai-operations-latency-section"
              >
                <h2 className="ac-ao-page__section-title">时延分布</h2>
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
                <h2 className="ac-ao-page__section-title">Token 用量</h2>
                <TokenUsageChart
                  rows={tokenQuery.data.rows}
                  versionSelector={versionSelectorData}
                />
              </section>
            )}
          </div>

          <div className="ac-ao-page__row">
            {costSummaryQuery.data && (
              <section
                className="ac-ao-page__panel"
                data-testid="ai-operations-cost-section"
              >
                <h2 className="ac-ao-page__section-title">成本概览</h2>
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

          {qualityIssuesQuery.data && (
            <section
              className="ac-ao-page__panel"
              data-testid="ai-operations-quality-issues-section"
            >
              <h2 className="ac-ao-page__section-title">AI 质量议题</h2>
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
