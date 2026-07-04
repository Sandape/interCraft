/**
 * FunnelChart — REQ-044 US2 / FR-012.
 *
 * Renders a 5-step funnel with count + step_conversion + drop_off +
 * entry_conversion + comparison_delta + time-to-convert P50/CI.
 *
 * Edge Cases handled:
 *
 *   - EC-1: zero funnel data surfaces an explicit "0 users entered"
 *     banner (FR-028 valid zero, no silent empty fallback).
 *   - AC-13.3: every panel renders the cohort tag, the population
 *     count, and the last_computed_at timestamp.
 */
import type { FunnelResponse } from '@/types/admin-product-analytics'

interface FunnelChartProps {
  funnel: FunnelResponse
  cohortName?: string | null
}

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function formatSignedPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const sign = value > 0 ? '+' : value < 0 ? '' : ''
  return `${sign}${(value * 100).toFixed(1)}%`
}

function formatSeconds(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(0)}s`
  if (seconds < 3600) return `${(seconds / 60).toFixed(0)}m`
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`
  return `${(seconds / 86400).toFixed(1)}d`
}

export function FunnelChart({ funnel, cohortName }: FunnelChartProps) {
  const totalEntered = funnel.steps[0]?.count ?? 0
  const isZero = totalEntered === 0

  return (
    <div className="ac-pa-funnel" data-testid="funnel-chart">
      <div className="ac-pa-funnel__meta">
        <span className="ac-pa-funnel__cohort" data-testid="funnel-cohort">
          {cohortName ?? funnel.cohortId ?? '全量'}
        </span>
        <span
          className="ac-pa-funnel__population"
          data-testid="funnel-cohort-population"
        >
          population {funnel.cohortPopulation.toLocaleString()}
        </span>
        <span
          className="ac-pa-funnel__freshness"
          data-testid="funnel-last-computed-at"
        >
          last computed {funnel.lastComputedAt}
        </span>
      </div>

      {isZero && (
        <div
          className="ac-pa-funnel__zero"
          data-testid="funnel-zero-banner"
          role="status"
        >
          <strong>0 users entered</strong> — valid zero per FR-028 (no silent
          fallback)
        </div>
      )}

      <ol className="ac-pa-funnel__steps">
        {funnel.steps.map((step, idx) => {
          const widthPct =
            totalEntered > 0
              ? Math.max(2, (step.count / totalEntered) * 100)
              : 0
          return (
            <li
              key={step.stepName}
              className="ac-pa-funnel__step"
              data-testid={`funnel-step-${step.stepName}`}
            >
              <div className="ac-pa-funnel__step-header">
                <span className="ac-pa-funnel__step-name">
                  {idx + 1}. {step.stepName}
                </span>
                <span
                  className="ac-pa-funnel__step-count"
                  data-testid={`funnel-step-${step.stepName}-count`}
                >
                  {step.count.toLocaleString()} users
                </span>
              </div>
              <div
                className="ac-pa-funnel__step-bar"
                style={{ width: `${widthPct}%` }}
                aria-hidden="true"
              />
              <div className="ac-pa-funnel__step-stats">
                <span data-testid={`funnel-step-${step.stepName}-conversion`}>
                  step conversion {formatPct(step.stepConversion)}
                </span>
                <span data-testid={`funnel-step-${step.stepName}-dropoff`}>
                  drop-off {formatPct(step.dropOff)}
                </span>
              </div>
            </li>
          )
        })}
      </ol>

      <div className="ac-pa-funnel__footer">
        <div
          className="ac-pa-funnel__entry"
          data-testid="funnel-entry-conversion"
        >
          <span className="ac-pa-funnel__label">Entry conversion</span>
          <span className="ac-pa-funnel__value">
            {formatPct(funnel.entryConversion)}
          </span>
        </div>
        {funnel.comparisonDelta && (
          <div
            className="ac-pa-funnel__comparison"
            data-testid="funnel-comparison-delta"
          >
            <span className="ac-pa-funnel__label">
              vs {funnel.comparisonDelta.comparisonPeriodLabel}
            </span>
            <span className="ac-pa-funnel__value">
              {formatSignedPct(funnel.comparisonDelta.stepConversionDelta)}
            </span>
          </div>
        )}
        {funnel.timeToConvert && (
          <div
            className="ac-pa-funnel__ttc"
            data-testid="funnel-time-to-convert"
          >
            <span className="ac-pa-funnel__label">Time to convert P50</span>
            <span className="ac-pa-funnel__value">
              {formatSeconds(funnel.timeToConvert.p50Seconds)} (
              {formatSeconds(funnel.timeToConvert.ci95LowerSeconds)}–
              {formatSeconds(funnel.timeToConvert.ci95UpperSeconds)})
            </span>
            <span className="ac-pa-funnel__sample">
              n = {funnel.timeToConvert.sampleSize}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default FunnelChart