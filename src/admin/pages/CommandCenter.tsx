/**
 * CommandCenter — REQ-044 FR-003 / US1.
 *
 * PM 决策指挥中心（FR-007~FR-010 + SC-001 + SC-002）。
 *
 * Layout:
 *
 *   - 顶部 4 KPI tiles (Product Health / AI Quality / AI Cost / System)
 *   - 中部 Decision Queue (按 priority desc + freshness_at desc 排序)
 *   - 右侧 Recent Reviews 面板（[CROSS-TEAM-DEBT] 空态）
 *   - 底部 QuietState (high_severity_count == 0 时显示)
 *   - SignalDrawer 详情侧栏 (click signal 展开)
 *
 * FR-010 quiet steady-state: 当 high_severity_count == 0 时显示
 * QuietState，不制造伪告警。
 */
import { useState } from 'react'
import {
  useDecisionSignals,
  useCommandCenterOverview,
} from '@/admin/hooks/queries/useDecisionSignals'
import type { DecisionSignal } from '@/types/admin-decision-signals'
import { DecisionSignalCard } from '@/admin/components/decision-signals/DecisionSignalCard'
import { DecisionSignalDrawer } from '@/admin/components/decision-signals/DecisionSignalDrawer'
import { QuietState } from '@/admin/components/decision-signals/QuietState'

function fmtNumber(value: number, unit: string): string {
  if (unit === 'usd') {
    return `$${value.toFixed(2)}`
  }
  if (unit === 'rate') {
    return `${(value * 100).toFixed(1)}%`
  }
  if (unit === 'score') {
    return value.toFixed(2)
  }
  return value.toFixed(2)
}

export function CommandCenter() {
  const overviewQuery = useCommandCenterOverview()
  const signalsQuery = useDecisionSignals()
  const [openSignal, setOpenSignal] = useState<DecisionSignal | null>(null)

  const response = signalsQuery.data
  const overview = overviewQuery.data?.overview

  return (
    <div className="ac-page" data-testid="command-center">
      <div className="ac-page__header">
        <h1 className="ac-page__title">Command Center</h1>
        <span className="ac-page__hint">
          PM 决策指挥中心 · 默认 landing · FR-007~FR-010
        </span>
      </div>

      <div className="ds-shell">
        {/* KPI tiles */}
        <section className="ds-kpis" data-testid="command-center-kpis">
          {overview ? (
            <>
              <div className="ds-kpi" data-testid="kpi-product-health">
                <span className="ds-kpi__label">Product Health</span>
                <span className="ds-kpi__value">
                  {fmtNumber(overview.productHealth, overview.productHealthUnit)}
                  <span className="ds-kpi__unit">
                    / {overview.productHealthUnit}
                  </span>
                </span>
              </div>
              <div className="ds-kpi" data-testid="kpi-ai-quality">
                <span className="ds-kpi__label">AI Quality</span>
                <span className="ds-kpi__value">
                  {fmtNumber(overview.aiQuality, overview.aiQualityUnit)}
                  <span className="ds-kpi__unit">{overview.aiQualityUnit}</span>
                </span>
              </div>
              <div className="ds-kpi" data-testid="kpi-ai-cost">
                <span className="ds-kpi__label">AI Cost</span>
                <span className="ds-kpi__value">
                  {fmtNumber(overview.aiCost, overview.aiCostUnit)}
                  <span className="ds-kpi__unit">{overview.aiCostUnit}</span>
                </span>
              </div>
              <div className="ds-kpi" data-testid="kpi-system-health">
                <span className="ds-kpi__label">System Health</span>
                <span className="ds-kpi__value">
                  {fmtNumber(overview.systemHealth, overview.systemHealthUnit)}
                  <span className="ds-kpi__unit">
                    / {overview.systemHealthUnit}
                  </span>
                </span>
              </div>
            </>
          ) : (
            <div className="ds-kpi" data-testid="kpi-loading">
              <span className="ds-kpi__label">Loading…</span>
            </div>
          )}
        </section>

        {/* Quiet state OR Decision queue + Recent reviews */}
        {response ? (
          response.quietSteadyState ? (
            <QuietState response={response} />
          ) : (
            <div className="ds-layout" data-testid="command-center-layout">
              <section
                className="ds-queue"
                data-testid="command-center-queue"
              >
                <div className="ds-queue__header">
                  <span className="ds-queue__title">Decision Queue</span>
                  <span
                    className="ds-queue__hint"
                    data-testid="command-center-queue-hint"
                  >
                    {response.total} signals · {response.highSeverityCount} high-severity
                  </span>
                </div>
                <div className="ds-queue__list">
                  {response.signals.map((s) => (
                    <DecisionSignalCard
                      key={s.id}
                      signal={s}
                      onOpen={setOpenSignal}
                    />
                  ))}
                </div>
              </section>
              <aside
                className="ds-reviews"
                data-testid="command-center-reviews"
              >
                <div className="ds-queue__header">
                  <span className="ds-queue__title">Recent Reviews</span>
                </div>
                <p
                  className="ds-quiet__no-signals"
                  data-testid="recent-reviews-empty"
                >
                  No recent reviews · [CROSS-TEAM-DEBT] Phase 2 batch 2
                  接 review_queue 表
                </p>
              </aside>
            </div>
          )
        ) : signalsQuery.isLoading ? (
          <div
            className="ds-quiet"
            data-testid="command-center-loading"
          >
            <span className="ds-quiet__lede">Loading decision queue…</span>
          </div>
        ) : signalsQuery.isError ? (
          <div className="ac-error-banner" data-testid="command-center-error">
            Failed to load decision signals.{' '}
            {signalsQuery.error instanceof Error
              ? signalsQuery.error.message
              : 'Unknown error'}
          </div>
        ) : null}
      </div>

      <DecisionSignalDrawer
        signal={openSignal}
        onClose={() => setOpenSignal(null)}
      />
    </div>
  )
}

export default CommandCenter