/**
 * ProductAnalytics — REQ-044 US2 / FR-011~FR-015.
 *
 * Phase 2 implementation. Renders the question-first Product
 * Analytics workspace:
 *
 *   - 7 question tabs (activation / funnel / retention / adoption /
 *     journey / release / experiment) — in-page state, no navigation
 *   - Per-tab template grid
 *   - Right-side CohortPicker (FR-013 / AC-13.2)
 *   - Funnel + FeatureAdoption panels share the selected cohortId
 *     (AC-13.2)
 *   - Metric tooltip with 7 SC-004 fields
 *   - Edge cases: zero funnel banner (EC-1), stale cohort warning
 *     (EC-2), insufficient data badge (EC-3)
 */
import { useMemo, useState } from 'react'
import {
  useCohorts,
  useFeatureAdoption,
  useFunnel,
  useQuestionTemplates,
} from '@/admin/hooks/queries/useProductAnalytics'
import { QuestionTabBar } from '@/admin/components/product-analytics/QuestionTabBar'
import { FunnelChart } from '@/admin/components/product-analytics/FunnelChart'
import { CohortPicker } from '@/admin/components/product-analytics/CohortPicker'
import { FeatureAdoptionGrid } from '@/admin/components/product-analytics/FeatureAdoptionGrid'
import { MetricTooltip } from '@/admin/components/product-analytics/MetricTooltip'
import type { QuestionTab } from '@/types/admin-product-analytics'

export function ProductAnalytics() {
  const [activeTab, setActiveTab] = useState<QuestionTab>('funnel')
  const [selectedCohortId, setSelectedCohortId] = useState<string | null>(
    null,
  )

  const templatesQuery = useQuestionTemplates()
  const cohortsQuery = useCohorts()
  const funnelQuery = useFunnel({
    templateId: 'q-fun-1',
    cohortId: selectedCohortId,
  })
  const adoptionQuery = useFeatureAdoption({ cohortId: selectedCohortId })

  const templatesForTab = useMemo(
    () =>
      (templatesQuery.data?.templates ?? []).filter(
        (t) => t.tab === activeTab,
      ),
    [templatesQuery.data, activeTab],
  )

  const cohortName = useMemo(() => {
    if (!selectedCohortId) return null
    return (
      cohortsQuery.data?.cohorts.find((c) => c.id === selectedCohortId)
        ?.name ?? null
    )
  }, [cohortsQuery.data, selectedCohortId])

  return (
    <div
      className="ac-page ac-pa-page"
      data-testid="product-analytics"
    >
      <div className="ac-page__header">
        <h1 className="ac-page__title">产品分析</h1>
        <span className="ac-page__hint">
          问题驱动分析 · 漏斗 · 队列 · 留存 · 功能采用
        </span>
      </div>

      <QuestionTabBar activeTab={activeTab} onChange={setActiveTab} />

      <div className="ac-pa-page__layout">
        <main className="ac-pa-page__main">
          <section
            className="ac-pa-page__templates"
            data-testid="product-analytics-templates"
          >
            <h2 className="ac-pa-page__section-title">
              Templates · {activeTab} ({templatesForTab.length})
            </h2>
            {templatesForTab.length === 0 ? (
              <div
                className="ac-pa-page__empty"
                data-testid="product-analytics-templates-empty"
              >
                暂无模板
              </div>
            ) : (
              <ul className="ac-pa-page__template-list">
                {templatesForTab.map((t) => (
                  <li
                    key={t.templateId}
                    className="ac-pa-page__template"
                    data-testid={`product-analytics-template-${t.templateId}`}
                  >
                    <MetricTooltip
                      trigger={
                        <span className="ac-pa-page__template-title">
                          {t.title}
                        </span>
                      }
                      definition={t.description}
                      owner={t.owner}
                      source={t.metricId}
                      period={`${t.requiredPeriodDays}d`}
                      freshness={t.freshnessAt}
                      completeness={
                        t.requiredCohortId ? 'cohort-scoped' : 'unfiltered'
                      }
                      qualityFlag="valid"
                    />
                    <div className="ac-pa-page__template-meta">
                      <span>metric {t.metricId}</span>
                      <span>period {t.requiredPeriodDays}d</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {activeTab === 'funnel' && (
            <section
              className="ac-pa-page__panel"
              data-testid="product-analytics-funnel-panel"
            >
              <h2 className="ac-pa-page__section-title">Funnel</h2>
              {funnelQuery.isLoading ? (
                <div data-testid="funnel-loading">加载中...</div>
              ) : funnelQuery.isError ? (
                <div data-testid="funnel-error">加载失败</div>
              ) : funnelQuery.data ? (
                <FunnelChart
                  funnel={funnelQuery.data}
                  cohortName={cohortName}
                />
              ) : null}
            </section>
          )}

          {activeTab === 'adoption' && (
            <section
              className="ac-pa-page__panel"
              data-testid="product-analytics-adoption-panel"
            >
              <h2 className="ac-pa-page__section-title">Feature Adoption</h2>
              {adoptionQuery.isLoading ? (
                <div data-testid="adoption-loading">加载中...</div>
              ) : adoptionQuery.isError ? (
                <div data-testid="adoption-error">加载失败</div>
              ) : adoptionQuery.data ? (
                <FeatureAdoptionGrid rows={adoptionQuery.data.features} />
              ) : null}
            </section>
          )}

          {!['funnel', 'adoption'].includes(activeTab) && (
            <section
              className="ac-pa-page__panel"
              data-testid="product-analytics-tab-placeholder"
            >
              <h2 className="ac-pa-page__section-title">{activeTab}</h2>
              <div className="ac-pa-page__empty">
                视图模板已就绪 · 详细面板将在 Phase 2 batch 2 接入
              </div>
            </section>
          )}
        </main>

        <aside
          className="ac-pa-page__sidebar"
          data-testid="product-analytics-sidebar"
        >
          <h2 className="ac-pa-page__section-title">Cohort</h2>
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
        </aside>
      </div>
    </div>
  )
}

export default ProductAnalytics