/**
 * REQ-061 (US8 / T057) — Point ledger table with task/milestone deep links.
 * No RMB / purchase controls.
 */
import { Link } from 'react-router-dom'
import { Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useAIPointLedger } from '@/hooks/queries/useAIPoints'
import type { ListAIPointLedgerQuery, PointEventType } from '@/types/ai-metering'
import { cn } from '@/lib/utils'

const EVENT_LABELS: Record<PointEventType, string> = {
  grant: '发放',
  expire: '失效',
  reserve: '预留',
  settle: '结算',
  release: '释放',
  refund: '退回',
  compensate: '补偿',
  reverse: '冲正',
}

function formatDelta(n: number): string {
  if (n > 0) return `+${n.toLocaleString()}`
  return n.toLocaleString()
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN')
}

export interface AIPointLedgerProps {
  filters?: ListAIPointLedgerQuery
  className?: string
}

export function AIPointLedger({ filters = {}, className }: AIPointLedgerProps) {
  const { data, isLoading, isError, error, refetch, isFetching } = useAIPointLedger({
    limit: 20,
    ...filters,
  })

  if (isLoading) {
    return (
      <div
        className={cn('flex items-center justify-center gap-2 py-10 text-sm text-ink-3', className)}
        data-testid="ai-point-ledger-loading"
      >
        <Loader2 className="h-4 w-4 animate-spin" />
        加载点数明细…
      </div>
    )
  }

  if (isError) {
    return (
      <div className={cn('space-y-3 py-6', className)} data-testid="ai-point-ledger-error">
        <p className="text-sm text-ink-2">明细加载失败，请稍后重试。</p>
        <p className="text-xs text-ink-3">
          {error instanceof Error ? error.message : '网络或服务暂时不可用'}
        </p>
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />}
          onClick={() => refetch()}
          disabled={isFetching}
        >
          重试
        </Button>
      </div>
    )
  }

  const items = data?.items ?? []

  if (items.length === 0) {
    return (
      <div
        className={cn('rounded-md bg-surface-muted dark:bg-dark-surface-muted px-4 py-6 text-sm text-ink-3', className)}
        data-testid="ai-point-ledger-empty"
      >
        暂无点数变动记录。
      </div>
    )
  }

  return (
    <div className={cn('overflow-x-auto', className)} data-testid="ai-point-ledger">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead>
          <tr className="border-b border-surface-border dark:border-dark-surface-border text-2xs text-ink-3">
            <th className="pb-2 pr-3 font-medium">时间</th>
            <th className="pb-2 pr-3 font-medium">类型</th>
            <th className="pb-2 pr-3 font-medium">可用变动</th>
            <th className="pb-2 pr-3 font-medium">预留变动</th>
            <th className="pb-2 pr-3 font-medium">余额后</th>
            <th className="pb-2 pr-3 font-medium">任务 / 里程碑</th>
            <th className="pb-2 font-medium">说明</th>
          </tr>
        </thead>
        <tbody>
          {items.map((entry) => (
            <tr
              key={entry.event_id}
              className="border-b border-surface-border/60 dark:border-dark-surface-border/60 align-top"
            >
              <td className="py-2.5 pr-3 text-xs text-ink-3 whitespace-nowrap">
                {formatTime(entry.occurred_at)}
              </td>
              <td className="py-2.5 pr-3">
                <Badge variant="default">{EVENT_LABELS[entry.event_type] ?? entry.event_type}</Badge>
              </td>
              <td
                className={cn(
                  'py-2.5 pr-3 tabular-nums font-medium',
                  entry.available_delta > 0 && 'text-emerald-600 dark:text-emerald-400',
                  entry.available_delta < 0 && 'text-ink-1',
                )}
              >
                {formatDelta(entry.available_delta)}
              </td>
              <td className="py-2.5 pr-3 tabular-nums text-ink-2">
                {formatDelta(entry.reserved_delta)}
              </td>
              <td className="py-2.5 pr-3 tabular-nums text-ink-2">
                {entry.available_after.toLocaleString()}
                <span className="text-ink-muted text-2xs ml-1">
                  / 预留 {entry.reserved_after.toLocaleString()}
                </span>
              </td>
              <td className="py-2.5 pr-3">
                {entry.task_id ? (
                  <div className="space-y-0.5">
                    <Link
                      to={`/ai-tasks/${entry.task_id}`}
                      className="text-brand-600 dark:text-brand-300 hover:underline text-xs"
                      data-testid={`ai-point-ledger-task-${entry.task_id}`}
                    >
                      查看任务
                    </Link>
                    {entry.milestone_code && (
                      <div className="text-2xs text-ink-3">{entry.milestone_code}</div>
                    )}
                  </div>
                ) : (
                  <span className="text-xs text-ink-muted">—</span>
                )}
              </td>
              <td className="py-2.5 text-xs text-ink-2 max-w-[200px]">
                <span className="line-clamp-2">{entry.reason}</span>
                {entry.capability && (
                  <span className="mt-0.5 block text-2xs text-ink-muted">{entry.capability}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
