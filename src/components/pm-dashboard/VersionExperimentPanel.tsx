/** REQ-033 US7 T130 — VersionExperimentPanel.

Renders the 5th PM Dashboard V1 panel per US7 spec:

1. 5 metric cards (event_count + 4 distinct dimension counts)
2. Version breakdown table (top 5 rows by count desc)
3. Experiment breakdown table (top 5 rows by count desc)
4. "trace unavailable" badge when no OTel trace is active (US7 T123)

Privacy: only counts + breakdowns are surfaced. No raw event content.

Layout mirrors AIOperationsPanel (US4 T109): metric cards in a 4-col
grid + breakdown tables in a 2-col grid below.
*/
import { AlertTriangle, Info } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import type { VersionExperimentPanel } from '@/types/pm-dashboard'

interface VersionExperimentPanelProps {
  panel: VersionExperimentPanel
}

interface MetricCard {
  key: keyof VersionExperimentPanel['data']
  label: string
  format: 'int'
}

const METRIC_CARDS: MetricCard[] = [
  { key: 'event_count', label: '事件总数', format: 'int' },
  {
    key: 'distinct_prompt_fingerprints',
    label: 'Prompt 指纹数',
    format: 'int',
  },
  { key: 'distinct_models', label: '模型数', format: 'int' },
  { key: 'distinct_app_versions', label: 'App 版本数', format: 'int' },
  { key: 'distinct_experiments', label: '实验数', format: 'int' },
]

function formatValue(value: number): string {
  return value.toLocaleString('en-US')
}

export function VersionExperimentPanel({
  panel,
}: VersionExperimentPanelProps) {
  const data = panel.data ?? ({} as VersionExperimentPanel['data'])
  const qf = panel.quality_flags ?? {}
  const hasWarning =
    (qf.missing_version_fields?.length ?? 0) > 0 || qf.partial_data
  const traceUnavailable = data.trace_available === false
  const topVersions = data.top_versions ?? []
  const topExperiments = data.top_experiments ?? []

  return (
    <Card padding="lg" data-testid="version-experiment-panel">
      <CardHeader
        title="版本与实验 / Version & Experiment"
        description={
          <span className="flex items-center gap-2">
            <span>
              {panel.period_start} ~ {panel.period_end}
            </span>
            {traceUnavailable && (
              <span
                className="inline-flex items-center gap-1 text-amber-600"
                data-testid="version-experiment-trace-unavailable"
                aria-label="Trace unavailable"
              >
                <Info className="h-3 w-3" />
                <span className="text-xs">trace unavailable</span>
              </span>
            )}
            {hasWarning && (
              <span
                className="inline-flex items-center gap-1 text-amber-600"
                data-testid="version-experiment-quality-warning"
                aria-label="Quality warning"
              >
                <AlertTriangle className="h-3 w-3" />
                <span className="text-xs">数据不完整</span>
              </span>
            )}
          </span>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {METRIC_CARDS.map((card) => {
          const v = Number(data[card.key] ?? 0)
          return (
            <div
              key={card.key}
              data-testid={`version-experiment-metric-${card.key}`}
              className="rounded-md border border-surface-border dark:border-dark-surface-border bg-surface-muted dark:bg-dark-surface-muted p-3"
            >
              <div className="text-2xs uppercase tracking-wide">{card.label}</div>
              <div className="mt-1 text-xl font-semibold">
                <span>{formatValue(v)}</span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Version breakdown table — top 5 by event count desc */}
      <div
        className="mt-3 rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface p-2"
        data-testid="version-experiment-version-breakdown"
      >
        <div className="text-2xs uppercase tracking-wide text-ink-3 mb-1">
          按版本 (prompt × rubric × app × model) Top {topVersions.length}
        </div>
        {topVersions.length === 0 ? (
          <div
            className="text-2xs text-ink-3"
            data-testid="version-experiment-version-empty"
          >
            暂无数据
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-2xs uppercase tracking-wide text-ink-3">
                <th className="text-left">Prompt 指纹</th>
                <th className="text-left">Rubric</th>
                <th className="text-left">App</th>
                <th className="text-left">Model</th>
                <th className="text-right">Count</th>
              </tr>
            </thead>
            <tbody>
              {topVersions.map((row, idx) => {
                const key = `${row.prompt_fingerprint}-${row.rubric_version}-${row.app_version}-${row.model}`
                return (
                  <tr
                    key={key}
                    data-testid="version-experiment-version-row"
                    className="border-t border-surface-border dark:border-dark-surface-border"
                  >
                    <td className="py-0.5 truncate" title={row.prompt_fingerprint}>
                      {row.prompt_fingerprint}
                    </td>
                    <td className="py-0.5">{row.rubric_version}</td>
                    <td className="py-0.5">{row.app_version}</td>
                    <td className="py-0.5 truncate" title={row.model}>
                      {row.model}
                    </td>
                    <td className="py-0.5 text-right font-mono">
                      {row.count.toLocaleString('en-US')}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Experiment breakdown table — top 5 by event count desc */}
      <div
        className="mt-3 rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface p-2"
        data-testid="version-experiment-experiment-breakdown"
      >
        <div className="text-2xs uppercase tracking-wide text-ink-3 mb-1">
          按实验 (experiment_id) Top {topExperiments.length}
        </div>
        {topExperiments.length === 0 ? (
          <div
            className="text-2xs text-ink-3"
            data-testid="version-experiment-experiment-empty"
          >
            暂无数据
          </div>
        ) : (
          <ul className="text-xs space-y-0.5">
            {topExperiments.map((row) => {
              const key = `${row.experiment_id}`
              return (
                <li
                  key={key}
                  data-testid="version-experiment-experiment-row"
                  className="flex justify-between gap-2"
                >
                  <span className="truncate" title={row.experiment_id}>
                    {row.experiment_id}
                  </span>
                  <span className="font-mono">
                    {row.count.toLocaleString('en-US')}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between text-2xs text-ink-3">
        <span
          data-testid="version-experiment-source-of-truth"
        >
          数据来源: {panel.source_of_truth} | 最后更新:{' '}
          {panel.freshness_at === 'unknown'
            ? 'unknown (无数据)'
            : panel.freshness_at}
        </span>
        {qf.missing_version_fields && qf.missing_version_fields.length > 0 && (
          <span
            className="inline-flex items-center gap-1"
            data-testid="version-experiment-missing-fields"
          >
            <Info className="h-3 w-3" />
            缺失版本字段: {qf.missing_version_fields.join(', ')}
          </span>
        )}
      </div>
    </Card>
  )
}