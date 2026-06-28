/** REQ-033 US1 T079 — FunnelPanel.
 *
 * Renders a horizontal funnel visualization with the 4 core funnel steps:
 *
 * - registered (auth.registered)
 * - active_users (product.visit)
 * - completed_ai_tasks (ai.call_completed)
 * - ai_success_rate (ai.call_completed)
 *
 * Each row shows: step name, count, conversion from previous step,
 * conversion from entry, and a "largest drop-off" indicator.
 *
 * Uses simple CSS bars (no chart library dependency) so the panel renders
 * even when recharts is unavailable. The bar widths are normalized to
 * the entry step's count.
 */
import { Card, CardHeader } from '@/components/ui/Card'
import { TrendingDown } from 'lucide-react'
import type { FunnelPanel } from '@/types/pm-dashboard'

interface FunnelPanelProps {
  panel: FunnelPanel
}

const STEP_LABELS: Record<string, string> = {
  registered: '注册用户',
  active_users: '活跃用户',
  completed_ai_tasks: '完成 AI 任务',
  ai_success_rate: 'AI 成功',
}

function labelFor(stepName: string): string {
  return STEP_LABELS[stepName] ?? stepName
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

export function FunnelPanel({ panel }: FunnelPanelProps) {
  const { steps, total_entry, total_completion } = panel.data
  const qf = panel.quality_flags ?? {}
  const hasWarning =
    (qf.missing_version_fields?.length ?? 0) > 0 || qf.partial_data

  return (
    <Card padding="lg" data-testid="funnel-panel">
      <CardHeader
        title="核心漏斗 / Core Funnel"
        description={
          <span>
            {panel.period_start} ~ {panel.period_end} |{' '}
            {panel.freshness_at === 'unknown'
              ? '无数据'
              : `更新于 ${panel.freshness_at}`}
          </span>
        }
        action={
          hasWarning ? (
            <span
              className="inline-flex items-center gap-1 text-amber-600 text-xs"
              data-testid="funnel-quality-warning"
            >
              <TrendingDown className="h-3 w-3" />
              数据不完整
            </span>
          ) : undefined
        }
      />

      {steps.length === 0 ? (
        <div
          className="text-sm text-ink-3 py-6 text-center"
          data-testid="funnel-empty"
        >
          暂无漏斗数据 (zero-state,非产品故障)
        </div>
      ) : (
        <div className="space-y-2" data-testid="funnel-rows">
          {steps.map((s) => {
            const widthPct =
              total_entry > 0 ? Math.max(2, (s.count / total_entry) * 100) : 2
            return (
              <div
                key={s.step_name}
                data-testid={`funnel-step-${s.step_name}`}
                className="flex items-center gap-3"
              >
                <div className="w-32 text-xs text-ink-2 flex-shrink-0">
                  {labelFor(s.step_name)}
                </div>
                <div className="flex-1 relative h-7 rounded bg-surface-muted dark:bg-dark-surface-muted overflow-hidden">
                  <div
                    className={`h-full rounded transition-[width] duration-300 ${
                      s.largest_drop_off
                        ? 'bg-amber-500/80'
                        : 'bg-brand-500/80'
                    }`}
                    style={{ width: `${widthPct}%` }}
                  />
                  <div className="absolute inset-0 flex items-center px-2 text-xs font-medium text-ink-1">
                    {s.count.toLocaleString('en-US')}
                  </div>
                </div>
                <div className="w-28 text-2xs text-ink-3 flex-shrink-0 text-right">
                  <div>转化自上一步: {pct(s.conversion_from_previous)}</div>
                  <div>转化自入口: {pct(s.conversion_from_entry)}</div>
                </div>
                {s.largest_drop_off && (
                  <span
                    className="text-2xs text-amber-600 font-medium"
                    data-testid="funnel-largest-drop"
                  >
                    最大流失
                  </span>
                )}
              </div>
            )
          })}
        </div>
      )}

      <div className="mt-3 flex items-center justify-between text-2xs text-ink-3">
        <span>
          总入口: {total_entry.toLocaleString('en-US')} | 总完成:{' '}
          {total_completion.toLocaleString('en-US')}
        </span>
        <span>数据来源: {panel.source_of_truth}</span>
      </div>
    </Card>
  )
}