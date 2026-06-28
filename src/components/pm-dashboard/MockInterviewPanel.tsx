/** REQ-033 US3 T097 — MockInterviewPanel.
 *
 * Renders the 5 core mock interview metrics per US3:
 *
 * 1. Session starts (count)
 * 2. Completions (count)
 * 3. Completion rate (completions / starts) — color-coded green >= 80%, amber 50-80%, red < 50%
 * 4. Avg question count (decimal)
 * 5. Failure rate (failures / starts) — color-coded green < 10%, amber 10-30%, red >= 30%
 * Plus: Report views (count).
 *
 * Privacy: the panel renders counts + rates + aggregate question count
 * only. No raw interview content (questions / answers / transcript /
 * audio) is ever surfaced here.
 *
 * Each card shows: display_name, value (formatted with unit), period,
 * freshness_at, and quality flags (warning icon if any
 * missing_version_fields or partial_data is set).
 */
import { AlertTriangle, Info } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import type { MockInterviewPanel } from '@/types/pm-dashboard'

interface MockInterviewPanelProps {
  panel: MockInterviewPanel
}

interface MetricCard {
  key: keyof MockInterviewPanel['data']
  label: string
  format: 'int' | 'percent' | 'decimal'
}

const METRIC_CARDS: MetricCard[] = [
  { key: 'starts', label: '面试启动数', format: 'int' },
  { key: 'completions', label: '完成数', format: 'int' },
  { key: 'completion_rate', label: '完成率', format: 'percent' },
  { key: 'avg_question_count', label: '平均题目数', format: 'decimal' },
  { key: 'report_views', label: '报告查看次数', format: 'int' },
  { key: 'failure_rate', label: '失败率', format: 'percent' },
]

function formatValue(
  value: number,
  format: MetricCard['format'],
): string {
  if (format === 'percent') return `${(value * 100).toFixed(1)}%`
  if (format === 'decimal') return value.toFixed(1)
  return value.toLocaleString('en-US')
}

function completionRateClass(rate: number): string {
  if (rate >= 0.8) return 'text-emerald-600 dark:text-emerald-400'
  if (rate >= 0.5) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-600 dark:text-red-400'
}

function failureRateClass(rate: number): string {
  // Lower is better for failure rate; invert the color band.
  if (rate < 0.1) return 'text-emerald-600 dark:text-emerald-400'
  if (rate < 0.3) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-600 dark:text-red-400'
}

export function MockInterviewPanel({ panel }: MockInterviewPanelProps) {
  const data = panel.data
  const qf = panel.quality_flags ?? {}
  const hasWarning =
    (qf.missing_version_fields?.length ?? 0) > 0 || qf.partial_data

  return (
    <Card padding="lg" data-testid="mock-interview-panel">
      <CardHeader
        title="模拟面试 / Mock Interview"
        description={
          <span className="flex items-center gap-2">
            <span>
              {panel.period_start} ~ {panel.period_end}
            </span>
            {hasWarning && (
              <span
                className="inline-flex items-center gap-1 text-amber-600"
                data-testid="mock-interview-quality-warning"
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
          let colorClass = ''
          if (card.format === 'percent') {
            if (card.key === 'completion_rate') {
              colorClass = completionRateClass(v)
            } else if (card.key === 'failure_rate') {
              colorClass = failureRateClass(v)
            }
          }
          return (
            <div
              key={card.key}
              data-testid={`mock-interview-metric-${card.key}`}
              className={`rounded-md border border-surface-border dark:border-dark-surface-border bg-surface-muted dark:bg-dark-surface-muted p-3 ${colorClass}`}
            >
              <div className="text-2xs uppercase tracking-wide">
                {card.label}
              </div>
              <div className="mt-1 text-xl font-semibold">
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
            data-testid="mock-interview-missing-fields"
          >
            <Info className="h-3 w-3" />
            缺失版本字段: {qf.missing_version_fields.join(', ')}
          </span>
        )}
      </div>
    </Card>
  )
}