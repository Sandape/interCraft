/** REQ-033 US1 T078 — OverviewPanel.
 *
 * Renders 8 metric cards covering FR-002:
 *
 * - UV (visits)
 * - Registered users
 * - Active users
 * - Completed AI tasks
 * - AI success rate
 * - Total tokens
 * - Estimated cost (labeled as estimate per FR-008)
 * - Open badcases
 *
 * Each card shows: display_name, value (formatted with unit), period,
 * freshness_at, and quality flags (warning icon if any
 * missing_version_fields or partial_data is set).
 */
import { AlertTriangle, Info } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import type { OverviewPanel } from '@/types/pm-dashboard'

interface OverviewPanelProps {
  panel: OverviewPanel
}

interface MetricCard {
  key: keyof OverviewPanel['data']
  label: string
  format: 'int' | 'percent' | 'currency' | 'tokens'
}

const METRIC_CARDS: MetricCard[] = [
  { key: 'uv', label: 'UV (访问量)', format: 'int' },
  { key: 'registered_users', label: '注册用户', format: 'int' },
  { key: 'active_users', label: '活跃用户', format: 'int' },
  { key: 'completed_ai_tasks', label: '已完成 AI 任务', format: 'int' },
  { key: 'ai_success_rate', label: 'AI 成功率', format: 'percent' },
  { key: 'total_tokens', label: 'Token 总量', format: 'tokens' },
  { key: 'estimated_cost', label: '估算成本 (USD)', format: 'currency' },
  { key: 'open_badcases', label: '未关闭 Badcase', format: 'int' },
]

function formatValue(value: number, format: MetricCard['format']): string {
  if (format === 'percent') return `${(value * 100).toFixed(1)}%`
  if (format === 'currency') return `$${value.toFixed(2)}`
  if (format === 'tokens') return value.toLocaleString('en-US')
  return value.toLocaleString('en-US')
}

export function OverviewPanel({ panel }: OverviewPanelProps) {
  const data = panel.data
  const qf = panel.quality_flags ?? {}
  const hasWarning =
    (qf.missing_version_fields?.length ?? 0) > 0 || qf.partial_data

  return (
    <Card padding="lg" data-testid="overview-panel">
      <CardHeader
        title="产品概览 / Product Overview"
        description={
          <span className="flex items-center gap-2">
            <span>
              {panel.period_start} ~ {panel.period_end}
            </span>
            {hasWarning && (
              <span
                className="inline-flex items-center gap-1 text-amber-600"
                data-testid="overview-quality-warning"
                aria-label="Quality warning"
              >
                <AlertTriangle className="h-3 w-3" />
                <span className="text-xs">数据不完整</span>
              </span>
            )}
          </span>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {METRIC_CARDS.map((card) => {
          const v = data[card.key] as number
          return (
            <div
              key={card.key}
              data-testid={`overview-metric-${card.key}`}
              className="rounded-md border border-surface-border dark:border-dark-surface-border bg-surface-muted dark:bg-dark-surface-muted p-3"
            >
              <div className="text-2xs text-ink-3 uppercase tracking-wide">
                {card.label}
              </div>
              <div className="mt-1 text-xl font-semibold text-ink-1">
                {formatValue(v, card.format)}
                {card.key === 'estimated_cost' && data.is_estimate && (
                  <span
                    className="ml-1 text-2xs text-ink-3 font-normal"
                    data-testid="cost-estimate-flag"
                  >
                    (estimate)
                  </span>
                )}
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
            data-testid="overview-missing-fields"
          >
            <Info className="h-3 w-3" />
            缺失版本字段: {qf.missing_version_fields.join(', ')}
          </span>
        )}
      </div>
    </Card>
  )
}