/**
 * REQ-061 (US1 / T034) — AI task detail.
 *
 * Shows server-derived status/actions, milestones, events, and failure panel.
 */
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2, RefreshCw } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import {
  AIFailurePanel,
  AIMilestoneList,
  AITaskStatus,
} from '@/components/ai'
import { useAITask, useAITaskEvents } from '@/hooks/queries/useAITasks'
import { cn } from '@/lib/utils'

const CAPABILITY_LABELS: Record<string, string> = {
  resume_intelligence: '简历智能',
  resume_derive: '简历派生',
  interview: '模拟面试',
  general_coach: '通用教练',
  error_coach: '错题教练',
  ability_insight: '画像洞察',
  proactive_research: '主动研究',
  wechat_agent: '微信 Agent',
}

function capabilityLabel(code: string): string {
  return CAPABILITY_LABELS[code] ?? code
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN')
}

export default function AITaskDetail() {
  const { taskId } = useParams<{ taskId: string }>()
  const {
    data: task,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useAITask(taskId)
  const eventsState = useAITaskEvents(taskId, { enabled: Boolean(taskId) })

  if (!taskId) {
    return (
      <div className="px-4 py-5 sm:px-6 lg:px-8 max-w-4xl mx-auto" data-testid="ai-task-detail-missing">
        <p className="text-sm text-ink-3">缺少任务 ID</p>
        <Link to="/ai-tasks" className="text-sm text-brand-600 mt-2 inline-block">
          返回任务中心
        </Link>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center" data-testid="ai-task-detail-loading">
        <Loader2 className="h-6 w-6 animate-spin text-ink-3" />
      </div>
    )
  }

  if (isError || !task) {
    return (
      <div className="px-4 py-5 sm:px-6 lg:px-8 max-w-4xl mx-auto" data-testid="ai-task-detail-error">
        <Card>
          <p className="text-sm text-danger-600 dark:text-danger-400">
            {error instanceof Error ? error.message : '加载任务详情失败'}
          </p>
          <div className="mt-3 flex gap-2">
            <Button variant="secondary" onClick={() => void refetch()}>
              重试
            </Button>
            <Link to="/ai-tasks">
              <Button variant="ghost">返回任务中心</Button>
            </Link>
          </div>
        </Card>
      </div>
    )
  }

  const title =
    task.title?.trim() || `${capabilityLabel(task.capability)} · ${task.action}`

  return (
    <div
      className="px-4 py-5 sm:px-6 lg:px-8 lg:py-6 max-w-4xl mx-auto space-y-4"
      data-testid="ai-task-detail"
      data-task-id={task.task_id}
      data-status={task.status}
      data-terminal={task.terminal ? 'true' : 'false'}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-2">
          <Link
            to="/ai-tasks"
            className="inline-flex items-center gap-1 text-xs text-ink-3 hover:text-ink-1"
            data-testid="ai-task-detail-back"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            返回任务中心
          </Link>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight truncate">
            {title}
          </h1>
          <div className="flex flex-wrap gap-2 text-xs text-ink-3">
            <Badge variant="outline">{capabilityLabel(task.capability)}</Badge>
            <span>动作 {task.action}</span>
            <span>档位 {task.service_tier === 'quality' ? '高质量' : '标准'}</span>
            <span>版本 v{task.task_version}</span>
            <span className="font-mono truncate" title={task.task_id}>
              {task.task_id}
            </span>
          </div>
        </div>
        <Button
          variant="ghost"
          leftIcon={
            isFetching || eventsState.isFetching ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )
          }
          onClick={() => {
            void refetch()
            eventsState.refetch()
          }}
          data-testid="ai-task-detail-refresh"
        >
          刷新
        </Button>
      </div>

      <Card data-testid="ai-task-detail-status">
        <CardHeader title="状态与进度" description={`受理于 ${formatTime(task.accepted_at)}`} />
        <AITaskStatus task={task} />
        {task.degraded && (
          <p
            className="mt-3 text-sm text-warning-700 dark:text-warning-400"
            data-testid="ai-task-detail-degraded"
          >
            已降级{task.degradation_summary ? `：${task.degradation_summary}` : ''}
          </p>
        )}
        {task.result_ref && (
          <p className="mt-2 text-xs text-ink-3 truncate" title={task.result_ref}>
            结果引用 {task.result_ref}
          </p>
        )}
      </Card>

      {task.failure && (
        <AIFailurePanel failure={task.failure} />
      )}

      <Card data-testid="ai-task-detail-milestones">
        <CardHeader title="里程碑" description="按服务端顺序展示，交付后不可回退" />
        <AIMilestoneList milestones={task.milestones} />
      </Card>

      <Card data-testid="ai-task-detail-events">
        <CardHeader
          title="事件时间线"
          description={
            eventsState.terminal
              ? '任务已终态，事件流已停止轮询'
              : '非终态任务会自动刷新事件'
          }
        />
        {eventsState.isLoading && eventsState.events.length === 0 && (
          <div className="flex items-center gap-2 text-sm text-ink-3 py-4">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载事件…
          </div>
        )}
        {eventsState.isError && (
          <div className="space-y-2">
            <p className="text-sm text-danger-600 dark:text-danger-400">
              {eventsState.error?.message ?? '加载事件失败'}
            </p>
            <Button variant="secondary" onClick={() => eventsState.refetch()}>
              重试事件
            </Button>
          </div>
        )}
        {!eventsState.isLoading && !eventsState.isError && eventsState.events.length === 0 && (
          <p className="text-sm text-ink-3" data-testid="ai-task-detail-events-empty">
            暂无事件
          </p>
        )}
        {eventsState.events.length > 0 && (
          <ol className="space-y-2" data-testid="ai-task-detail-events-list">
            {eventsState.events.map((event) => (
              <li
                key={event.event_id}
                className={cn(
                  'rounded border border-surface-border dark:border-dark-surface-border',
                  'px-3 py-2',
                )}
                data-testid="ai-task-event-item"
                data-sequence={event.sequence}
                data-event-type={event.event_type}
              >
                <div className="flex flex-wrap items-center gap-2 text-xs text-ink-3">
                  <span className="font-mono">#{event.sequence}</span>
                  <Badge variant="outline">{event.event_type}</Badge>
                  <span>{formatTime(event.occurred_at)}</span>
                  <span>{event.stage.label}</span>
                </div>
                <p className="mt-1 text-sm text-ink-2 dark:text-dark-ink-secondary">
                  {event.message}
                </p>
              </li>
            ))}
          </ol>
        )}
      </Card>

      {task.executions.length > 0 && (
        <Card data-testid="ai-task-detail-executions">
          <CardHeader title="执行谱系" description={`自动重试 ${task.automatic_retry_count} 次`} />
          <ul className="space-y-2">
            {task.executions.map((exec) => (
              <li
                key={exec.execution_id}
                className="rounded border border-surface-border dark:border-dark-surface-border px-3 py-2 text-sm"
                data-testid="ai-task-execution-item"
                data-execution-no={exec.execution_no}
              >
                <div className="flex flex-wrap gap-2 text-xs text-ink-3">
                  <span>#{exec.execution_no}</span>
                  <Badge variant="outline">{exec.trigger_kind}</Badge>
                  <span>{exec.status}</span>
                  <span>开始 {formatTime(exec.started_at)}</span>
                  {exec.finished_at && <span>结束 {formatTime(exec.finished_at)}</span>}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}