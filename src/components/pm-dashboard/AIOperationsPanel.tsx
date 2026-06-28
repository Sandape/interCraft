/** REQ-033 US4 T109 — AIOperationsPanel.
 *
 * Renders the 7 core AI operations metrics per US4:
 *
 * 1. Call count (total invocations)
 * 2. Success / failure counts (split by status) + rates
 * 3. Retry count (rows where retry_count > 0)
 * 4. Latency: P50 / P95 / P99 in ms
 * 5. Estimated cost (sum, labeled as estimate per FR-008)
 * 6. Token usage: prompt + completion
 * 7. Breakdown by model / graph / node / prompt_fingerprint (top 5)
 *
 * Privacy: the panel renders counts + rates + aggregates + top-N
 * breakdowns only. No raw AI content (prompt_text / completion_text /
 * system_prompt / messages / tool_calls / request_body / response_body)
 * is ever surfaced here. Per FR-008, the cost is labeled as an
 * estimate (is_estimate=true).
 */
import { AlertTriangle, Info } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import type { AIOperationsPanel } from '@/types/pm-dashboard'

interface AIOperationsPanelProps {
  panel: AIOperationsPanel
}

interface MetricCard {
  key: keyof AIOperationsPanel['data']
  label: string
  format: 'int' | 'percent' | 'ms' | 'currency' | 'tokens'
}

const METRIC_CARDS: MetricCard[] = [
  { key: 'call_count', label: 'AI 调用总数', format: 'int' },
  { key: 'success_rate', label: '成功率', format: 'percent' },
  { key: 'failure_rate', label: '失败率', format: 'percent' },
  { key: 'retry_count', label: '重试次数', format: 'int' },
  { key: 'p50_latency_ms', label: 'P50 延迟 (ms)', format: 'ms' },
  { key: 'p95_latency_ms', label: 'P95 延迟 (ms)', format: 'ms' },
  { key: 'estimated_cost', label: '估算成本 (USD)', format: 'currency' },
  { key: 'total_tokens', label: 'Token 总数', format: 'tokens' },
]

const BREAKDOWN_DIMENSIONS: Array<{
  key: keyof AIOperationsPanel['data']
  label: string
  testid: string
}> = [
  { key: 'model_breakdown', label: '模型', testid: 'model' },
  { key: 'graph_breakdown', label: '图', testid: 'graph' },
  { key: 'node_breakdown', label: '节点', testid: 'node' },
  { key: 'prompt_fingerprint_breakdown', label: 'Prompt 指纹', testid: 'fingerprint' },
]

function formatValue(
  value: number,
  format: MetricCard['format'],
): string {
  if (format === 'percent') return `${(value * 100).toFixed(1)}%`
  if (format === 'ms') return `${value.toFixed(0)} ms`
  if (format === 'currency') {
    // Show 4 decimals for sub-cent costs so PM sees the actual value.
    return `$${value.toFixed(4)}`
  }
  if (format === 'tokens') return value.toLocaleString('en-US')
  return value.toLocaleString('en-US')
}

function successRateClass(rate: number): string {
  if (rate >= 0.95) return 'text-emerald-600 dark:text-emerald-400'
  if (rate >= 0.8) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-600 dark:text-red-400'
}

function failureRateClass(rate: number): string {
  // Lower is better for failure rate; invert the color band.
  if (rate < 0.05) return 'text-emerald-600 dark:text-emerald-400'
  if (rate < 0.2) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-600 dark:text-red-400'
}

export function AIOperationsPanel({ panel }: AIOperationsPanelProps) {
  const data = panel.data
  const qf = panel.quality_flags ?? {}
  const hasWarning =
    (qf.missing_version_fields?.length ?? 0) > 0 || qf.partial_data

  return (
    <Card padding="lg" data-testid="ai-operations-panel">
      <CardHeader
        title="AI 运营 / AI Operations"
        description={
          <span className="flex items-center gap-2">
            <span>
              {panel.period_start} ~ {panel.period_end}
            </span>
            {hasWarning && (
              <span
                className="inline-flex items-center gap-1 text-amber-600"
                data-testid="ai-operations-quality-warning"
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
          const v = Number(data[card.key] ?? 0)
          let colorClass = ''
          if (card.format === 'percent') {
            if (card.key === 'success_rate') {
              colorClass = successRateClass(v)
            } else if (card.key === 'failure_rate') {
              colorClass = failureRateClass(v)
            }
          }
          return (
            <div
              key={card.key}
              data-testid={`ai-operations-metric-${card.key}`}
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

      {/* Top-N breakdowns — kept as a compact 2-column grid below the
          primary cards. Each row is `{dim: count}` sorted by count desc. */}
      <div
        className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2"
        data-testid="ai-operations-breakdowns"
      >
        {BREAKDOWN_DIMENSIONS.map((dim) => {
          const raw = (data as unknown as Record<string, unknown>)[
            dim.key as string
          ]
          const entries: Array<[string, number]> = Array.isArray(raw)
            ? []
            : Object.entries((raw ?? {}) as Record<string, number>).sort(
                (a, b) => b[1] - a[1],
              )
          return (
            <div
              key={dim.key as string}
              className="rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface p-2"
              data-testid={`ai-operations-breakdown-${dim.testid}`}
            >
              <div className="text-2xs uppercase tracking-wide text-ink-3 mb-1">
                按{dim.label} Top {entries.length}
              </div>
              {entries.length === 0 ? (
                <div
                  className="text-2xs text-ink-3"
                  data-testid={`ai-operations-breakdown-${dim.testid}-empty`}
                >
                  暂无数据
                </div>
              ) : (
                <ul className="text-xs space-y-0.5">
                  {entries.map(([k, c]) => (
                    <li
                      key={k}
                      className="flex justify-between gap-2"
                      data-testid={`ai-operations-breakdown-${dim.testid}-row`}
                    >
                      <span className="truncate" title={k}>
                        {k}
                      </span>
                      <span className="font-mono">{c.toLocaleString('en-US')}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}
      </div>

      <div className="mt-3 flex items-center justify-between text-2xs text-ink-3">
        <span>
          数据来源: {panel.source_of_truth}
          {data.is_estimate ? ' | 成本为估算值 (FR-008)' : ''} | 最后更新:{' '}
          {panel.freshness_at === 'unknown'
            ? 'unknown (无数据)'
            : panel.freshness_at}
        </span>
        {qf.missing_version_fields && qf.missing_version_fields.length > 0 && (
          <span
            className="inline-flex items-center gap-1"
            data-testid="ai-operations-missing-fields"
          >
            <Info className="h-3 w-3" />
            缺失版本字段: {qf.missing_version_fields.join(', ')}
          </span>
        )}
      </div>
    </Card>
  )
}
