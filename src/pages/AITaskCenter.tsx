/**
 * REQ-061 (US1 / T034) — Global AI task center.
 *
 * Lists owner-scoped AI tasks with capability/status filters and links to detail.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, Loader2, RefreshCw } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { aiTaskStatusLabel } from '@/components/ai'
import { listAITasks } from '@/api/ai-runtime'
import { useAITasks } from '@/hooks/queries/useAITasks'
import type { TaskStatus, TaskSummary } from '@/types/ai-runtime'
import { cn } from '@/lib/utils'

const PAGE_LIMIT = 20

const CAPABILITY_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: '全部能力' },
  { value: 'resume_intelligence', label: '简历智能' },
  { value: 'resume_derive', label: '简历派生' },
  { value: 'interview', label: '模拟面试' },
  { value: 'general_coach', label: '通用教练' },
  { value: 'error_coach', label: '错题教练' },
  { value: 'ability_insight', label: '画像洞察' },
  { value: 'proactive_research', label: '主动研究' },
  { value: 'wechat_agent', label: '微信 Agent' },
]

const STATUS_OPTIONS: { value: '' | TaskStatus; label: string }[] = [
  { value: '', label: '全部状态' },
  { value: 'accepted', label: '已受理' },
  { value: 'queued', label: '排队中' },
  { value: 'running', label: '执行中' },
  { value: 'waiting_user', label: '等待你操作' },
  { value: 'retry_wait', label: '等待重试' },
  { value: 'cancelling', label: '取消中' },
  { value: 'result_confirming', label: '结果确认中' },
  { value: 'succeeded', label: '已成功' },
  { value: 'partially_succeeded', label: '部分成功' },
  { value: 'failed', label: '已失败' },
  { value: 'cancelled', label: '已取消' },
  { value: 'expired', label: '已过期' },
]

const CAPABILITY_LABELS: Record<string, string> = Object.fromEntries(
  CAPABILITY_OPTIONS.filter((o) => o.value).map((o) => [o.value, o.label]),
)

function capabilityLabel(code: string): string {
  return CAPABILITY_LABELS[code] ?? code
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN')
}

function isTaskStatus(value: string): value is TaskStatus {
  return STATUS_OPTIONS.some((o) => o.value === value && o.value !== '')
}

export default function AITaskCenter() {
  const [searchParams, setSearchParams] = useSearchParams()
  const capability = searchParams.get('capability') ?? ''
  const statusParam = searchParams.get('status') ?? ''
  const status = isTaskStatus(statusParam) ? statusParam : undefined

  const filters = useMemo(
    () => ({
      capability: capability || undefined,
      status,
      limit: PAGE_LIMIT,
    }),
    [capability, status],
  )

  const { data, isLoading, isError, error, refetch, isFetching } = useAITasks(filters)
  const [moreItems, setMoreItems] = useState<TaskSummary[]>([])
  const [moreCursor, setMoreCursor] = useState<string | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null)

  useEffect(() => {
    setMoreItems([])
    setMoreCursor(null)
    setLoadMoreError(null)
  }, [capability, status])

  const items = useMemo(
    () => [...(data?.items ?? []), ...moreItems],
    [data?.items, moreItems],
  )
  const nextCursor =
    moreItems.length > 0 ? moreCursor : (data?.next_cursor ?? null)

  function updateFilter(key: 'capability' | 'status', value: string) {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    setSearchParams(next, { replace: true })
  }

  async function handleLoadMore() {
    if (!nextCursor || loadingMore) return
    setLoadingMore(true)
    setLoadMoreError(null)
    try {
      const page = await listAITasks({
        ...filters,
        cursor: nextCursor,
      })
      setMoreItems((prev) => [...prev, ...page.items])
      setMoreCursor(page.next_cursor)
    } catch (err) {
      setLoadMoreError(err instanceof Error ? err.message : '加载更多失败')
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <div
      className="px-4 py-5 sm:px-6 lg:px-8 lg:py-6 max-w-7xl mx-auto"
      data-testid="ai-task-center"
    >
      <div className="flex flex-col items-stretch gap-4 mb-6 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">AI 任务中心</h1>
          <p className="text-sm text-ink-3 mt-1">
            查看近 90 天内的 AI 任务状态、进度与结果入口
          </p>
        </div>
        <Button
          variant="ghost"
          leftIcon={
            isFetching ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )
          }
          onClick={() => {
            setMoreItems([])
            setMoreCursor(null)
            void refetch()
          }}
          data-testid="ai-task-center-refresh"
        >
          刷新
        </Button>
      </div>

      <div
        className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-2 sm:max-w-xl"
        data-testid="ai-task-center-filters"
      >
        <label className="block">
          <span className="sr-only">按能力筛选</span>
          <select
            data-testid="ai-task-filter-capability"
            value={capability}
            onChange={(e) => updateFilter('capability', e.target.value)}
            className="h-9 w-full px-3 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 border border-surface-border dark:border-dark-surface-border focus:outline-none focus:ring-2 focus:ring-brand-500/30"
          >
            {CAPABILITY_OPTIONS.map((opt) => (
              <option key={opt.value || 'all'} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="sr-only">按状态筛选</span>
          <select
            data-testid="ai-task-filter-status"
            value={status ?? ''}
            onChange={(e) => updateFilter('status', e.target.value)}
            className="h-9 w-full px-3 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 border border-surface-border dark:border-dark-surface-border focus:outline-none focus:ring-2 focus:ring-brand-500/30"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value || 'all'} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16 text-ink-3">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      )}

      {isError && (
        <Card className="mb-4" data-testid="ai-task-center-error">
          <p className="text-sm text-danger-600 dark:text-danger-400">
            {error instanceof Error ? error.message : '加载任务列表失败'}
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => void refetch()}>
            重试
          </Button>
        </Card>
      )}

      {!isLoading && !isError && items.length === 0 && (
        <Card data-testid="ai-task-center-empty">
          <p className="text-sm text-ink-3">暂无匹配的 AI 任务</p>
        </Card>
      )}

      {!isLoading && items.length > 0 && (
        <ul className="space-y-2" data-testid="ai-task-center-list">
          {items.map((task) => (
            <li key={task.task_id}>
              <Link
                to={`/ai-tasks/${task.task_id}`}
                data-testid="ai-task-center-row"
                data-task-id={task.task_id}
                data-status={task.status}
                data-capability={task.capability}
                className={cn(
                  'flex items-start gap-3 rounded border border-surface-border dark:border-dark-surface-border',
                  'bg-surface dark:bg-dark-surface px-4 py-3',
                  'hover:bg-surface-muted dark:hover:bg-dark-surface-muted transition-colors',
                )}
              >
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-ink-1 dark:text-dark-ink-primary truncate">
                      {task.title?.trim() || `${capabilityLabel(task.capability)} · ${task.action}`}
                    </span>
                    <Badge variant="outline">{capabilityLabel(task.capability)}</Badge>
                    <Badge
                      variant={
                        task.status === 'succeeded'
                          ? 'success'
                          : task.status === 'failed'
                            ? 'danger'
                            : task.terminal
                              ? 'outline'
                              : 'brand'
                      }
                    >
                      {aiTaskStatusLabel(task.status)}
                    </Badge>
                    {task.terminal && <Badge variant="outline">已结束</Badge>}
                  </div>
                  <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-ink-3 dark:text-dark-ink-tertiary">
                    <span>{task.stage.label}</span>
                    <span>受理于 {formatTime(task.accepted_at)}</span>
                    {task.terminal_at && <span>结束于 {formatTime(task.terminal_at)}</span>}
                    <span>
                      点数 {task.point_summary.settled}/{task.point_summary.quoted_max}
                    </span>
                  </div>
                </div>
                <ArrowRight className="h-4 w-4 mt-1 shrink-0 text-ink-3" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      )}

      {nextCursor && (
        <div className="mt-4 flex flex-col items-center gap-2">
          {loadMoreError && (
            <p className="text-xs text-danger-600 dark:text-danger-400">{loadMoreError}</p>
          )}
          <Button
            variant="secondary"
            onClick={() => void handleLoadMore()}
            disabled={loadingMore}
            data-testid="ai-task-center-load-more"
          >
            {loadingMore ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                加载中…
              </>
            ) : (
              '加载更多'
            )}
          </Button>
        </div>
      )}
    </div>
  )
}