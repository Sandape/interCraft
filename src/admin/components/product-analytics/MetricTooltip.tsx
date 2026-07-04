/**
 * MetricTooltip — REQ-044 US2 / SC-004.
 *
 * Every metric in the Product Analytics workspace MUST expose the 7
 * SC-004 fields:
 *
 *   1. definition
 *   2. owner
 *   3. source
 *   4. period (start / end)
 *   5. freshness
 *   6. completeness
 *   7. quality_flag
 *
 * The component is a controlled popover triggered by hovering or
 * focusing the trigger element. It also renders a static summary
 * (always visible) so the 7-field list is observable without
 * interaction (Playwright can read it directly).
 */
interface MetricTooltipProps {
  trigger: React.ReactNode
  definition: string
  owner: string
  source: string
  period: string
  freshness: string
  completeness: string
  qualityFlag: string
}

export function MetricTooltip({
  trigger,
  definition,
  owner,
  source,
  period,
  freshness,
  completeness,
  qualityFlag,
}: MetricTooltipProps) {
  return (
    <span
      className="ac-pa-metric-tooltip"
      data-testid="metric-tooltip"
    >
      <span
        className="ac-pa-metric-tooltip__trigger"
        data-testid="metric-tooltip-trigger"
      >
        {trigger}
      </span>
      <span
        className="ac-pa-metric-tooltip__body"
        data-testid="metric-tooltip-body"
        role="tooltip"
      >
        <dl className="ac-pa-metric-tooltip__fields">
          <dt data-testid="metric-tooltip-field-definition">definition</dt>
          <dd data-testid="metric-tooltip-value-definition">{definition}</dd>
          <dt data-testid="metric-tooltip-field-owner">owner</dt>
          <dd data-testid="metric-tooltip-value-owner">{owner}</dd>
          <dt data-testid="metric-tooltip-field-source">source</dt>
          <dd data-testid="metric-tooltip-value-source">{source}</dd>
          <dt data-testid="metric-tooltip-field-period">period</dt>
          <dd data-testid="metric-tooltip-value-period">{period}</dd>
          <dt data-testid="metric-tooltip-field-freshness">freshness</dt>
          <dd data-testid="metric-tooltip-value-freshness">{freshness}</dd>
          <dt data-testid="metric-tooltip-field-completeness">
            completeness
          </dt>
          <dd data-testid="metric-tooltip-value-completeness">
            {completeness}
          </dd>
          <dt data-testid="metric-tooltip-field-quality-flag">
            quality_flag
          </dt>
          <dd data-testid="metric-tooltip-value-quality-flag">
            {qualityFlag}
          </dd>
        </dl>
      </span>
    </span>
  )
}

export default MetricTooltip