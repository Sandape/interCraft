/** REQ-033 US2 T088 — ResumeDiagnosisPanel.
 *
 * Renders the 5 core resume diagnosis metrics per US2:
 *
 * 1. Diagnosis success rate (large card, color-coded green >= 80%, amber 50-80%, red < 50%)
 * 2. Report views
 * 3. Suggestions shown (count)
 * 4. Suggestions accepted (count)
 * 5. Acceptance rate (accepted / shown) + score delta with up/down arrow
 *
 * Privacy: the panel renders counts + rates + aggregate scores only.
 * No raw resume content is ever surfaced here.
 *
 * Each card shows: display_name, value (formatted with unit), period,
 * freshness_at, and quality flags (warning icon if any
 * missing_version_fields or partial_data is set).
 */
import { AlertTriangle, ArrowDown, ArrowUp, Minus, Info } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import type { ResumeDiagnosisPanel } from '@/types/pm-dashboard'

interface ResumeDiagnosisPanelProps {
  panel: ResumeDiagnosisPanel
}

interface MetricCard {
  key: keyof ResumeDiagnosisPanel['data']
  label: string
  format: 'int' | 'percent' | 'delta' | 'decimal'
}

const METRIC_CARDS: MetricCard[] = [
  { key: 'success_rate', label: '诊断成功率', format: 'percent' },
  { key: 'report_views', label: '报告查看次数', format: 'int' },
  { key: 'suggestions_shown', label: '建议展示数', format: 'int' },
  { key: 'suggestions_accepted', label: '建议采纳数', format: 'int' },
  { key: 'acceptance_rate', label: '建议采纳率', format: 'percent' },
  { key: 'score_delta', label: '评分提升 (Δ)', format: 'delta' },
]

function formatValue(
  value: number,
  format: MetricCard['format'],
): string {
  if (format === 'percent') return `${(value * 100).toFixed(1)}%`
  if (format === 'decimal') return value.toFixed(2)
  if (format === 'delta') {
    const v = Number(value)
    const sign = v > 0 ? '+' : v < 0 ? '' : ''
    return `${sign}${v.toFixed(1)}`
  }
  return value.toLocaleString('en-US')
}

function trendIcon(value: number) {
  if (value > 0) return ArrowUp
  if (value < 0) return ArrowDown
  return Minus
}

function trendClass(value: number): string {
  if (value > 0) return 'text-emerald-600 dark:text-emerald-400'
  if (value < 0) return 'text-red-600 dark:text-red-400'
  return 'text-ink-3'
}

function successRateClass(rate: number): string {
  if (rate >= 0.8) return 'text-emerald-600 dark:text-emerald-400'
  if (rate >= 0.5) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-600 dark:text-red-400'
}

export function ResumeDiagnosisPanel({ panel }: ResumeDiagnosisPanelProps) {
  const data = panel.data
  const qf = panel.quality_flags ?? {}
  const hasWarning =
    (qf.missing_version_fields?.length ?? 0) > 0 || qf.partial_data

  return (
    <Card padding="lg" data-testid="resume-diagnosis-panel">
      <CardHeader
        title="简历诊断 / Resume Diagnosis"
        description={
          <span className="flex items-center gap-2">
            <span>
              {panel.period_start} ~ {panel.period_end}
            </span>
            {hasWarning && (
              <span
                className="inline-flex items-center gap-1 text-amber-600"
                data-testid="resume-diagnosis-quality-warning"
                aria-label="Quality warning"
              >
                <AlertTriangle className="h-3 w-3" />
                <span className="text-xs">数据不完整</span>
              </span>
            )}
          </span>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {METRIC_CARDS.map((card) => {
          const v = Number(data[card.key] ?? 0)
          const isDelta = card.format === 'delta'
          const isPercent = card.format === 'percent'
          const Icon = isDelta ? trendIcon(v) : null
          const colorClass = isDelta
            ? trendClass(v)
            : isPercent && card.key === 'success_rate'
            ? successRateClass(v)
            : ''
          return (
            <div
              key={card.key}
              data-testid={`resume-diagnosis-metric-${card.key}`}
              data-trend={
                isDelta ? (v > 0 ? 'up' : v < 0 ? 'down' : 'flat') : undefined
              }
              className={`rounded-md border border-surface-border dark:border-dark-surface-border bg-surface-muted dark:bg-dark-surface-muted p-3 ${colorClass}`}
            >
              <div className="text-2xs uppercase tracking-wide">
                {card.label}
              </div>
              <div className="mt-1 text-xl font-semibold inline-flex items-center gap-1">
                {isDelta && Icon && <Icon className="h-4 w-4" />}
                <span>{formatValue(v, card.format)}</span>
              </div>
            </div>
          )
        })}
      </div>

      <div className="mt-3 flex items-center justify-between text-2xs text-ink-3">
        <span>
          数据来源: {panel.source_of_truth} | 最后更新:{' '}
          {panel.freshness_at === 'unknown'
            ? 'unknown (无数据)'
            : panel.freshness_at}
        </span>
        {qf.missing_version_fields && qf.missing_version_fields.length > 0 && (
          <span
            className="inline-flex items-center gap-1"
            data-testid="resume-diagnosis-missing-fields"
          >
            <Info className="h-3 w-3" />
            缺失版本字段: {qf.missing_version_fields.join(', ')}
          </span>
        )}
      </div>
    </Card>
  )
}
