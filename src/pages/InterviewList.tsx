import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Plus,
  Search,
  MessageSquare,
  Sparkles,
  Calendar,
  Clock,
  BarChart3,
  Lightbulb,
  AlertCircle,
  Loader2,
  ArrowRight,
  PlayCircle,
  Trash2,
  X,
} from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Tabs } from '@/components/ui/Tabs'
import {
  useInterviewSessions,
  useDeleteInterviewSession,
} from '@/hooks/queries/useInterviewSessions'
import { useErrorQuestions } from '@/hooks/queries/useErrorQuestions'
import { formatDuration, timeAgo, cn } from '@/lib/utils'

function formatInterviewMode(mode: string | null | undefined): string {
  switch (mode) {
    case 'quick_drill':
      return '错题补漏'
    case 'full':
      return '完整面试'
    case 'doubao':
      return '豆包面试'
    case 'voice':
      return '语音'
    case 'text':
      return '文字'
    default:
      return mode || '面试'
  }
}

export default function InterviewList() {
  const [tab, setTab] = useState('history')
  const [search, setSearch] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; label: string } | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const { data: sessionsResp, isLoading: sessionsLoading } = useInterviewSessions()
  const { data: errorsResp, isLoading: errorsLoading } = useErrorQuestions()
  const deleteMutation = useDeleteInterviewSession()

  const sessions = sessionsResp?.data || []
  const errorQuestions = errorsResp?.data || []
  const normalizedSearch = search.trim().toLowerCase()
  const hasSearchQuery = normalizedSearch.length > 0

  const filtered = sessions.filter((s) => {
    if (!hasSearchQuery) return true
    return (
      (s.company || '').toLowerCase().includes(normalizedSearch) ||
      (s.position || '').toLowerCase().includes(normalizedSearch)
    )
  })

  const avgScore = sessions.length > 0
    ? Math.round(sessions.reduce((sum, s) => sum + (s.overall_score || s.score || 0), 0) / sessions.length)
    : 0
  const passRate = sessions.length > 0
    ? Math.round((sessions.filter((s) => (s.overall_score || s.score || 0) >= 80).length / sessions.length) * 100)
    : 0
  const totalMinutes = sessions.length > 0
    ? Math.round(sessions.reduce((sum, s) => sum + (s.duration_seconds || 0), 0) / 60)
    : 0

  if (sessionsLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-ink-3" />
      </div>
    )
  }

  return (
    <div className="px-4 py-5 sm:px-6 lg:px-8 lg:py-6 max-w-7xl mx-auto">
      {/* 页头 */}
      <div className="flex flex-col items-stretch gap-4 mb-6 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">模拟面试</h1>
          <p className="text-sm text-ink-3 mt-1">
            基于简历和目标岗位生成定制化面试题库，AI 全程实时反馈
          </p>
        </div>
        <div className="sm:flex-none">
          <Link to="/interview/mode" className="block">
            <Button variant="primary" leftIcon={<Plus className="h-3.5 w-3.5" />} className="w-full sm:w-auto">
              开始新面试
            </Button>
          </Link>
        </div>
      </div>

      {/* 关键指标 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard
          label="累计面试"
          value={sessions.length.toString()}
          suffix="场"
          trend={`${sessions.filter((s) => s.status === 'completed').length} 场已完成`}
        />
        <StatCard
          label="平均评分"
          value={avgScore.toString()}
          suffix="分"
          trend={sessions.length > 0 ? '已完成面试' : '暂无数据'}
        />
        <StatCard
          label="通过率"
          value={passRate.toString()}
          suffix="%"
          trend="≥80 分"
        />
        <StatCard
          label="练习时长"
          value={totalMinutes.toString()}
          suffix="分钟"
          trend="累计"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* 开始新面试 Hero */}
        <Card className="lg:col-span-2 p-6 bg-gradient-to-br from-brand-50/60 via-surface to-surface dark:from-brand-500/5 dark:via-dark-surface dark:to-dark-surface border-brand-200/60 dark:border-brand-500/20">
          <div className="flex flex-col items-start gap-4 sm:flex-row sm:gap-5">
            <div className="h-14 w-14 rounded-lg bg-gradient-to-br from-brand-900 to-brand-600 dark:from-brand-500 dark:to-brand-300 flex items-center justify-center flex-shrink-0 shadow-notion">
              <Sparkles className="h-6 w-6 text-white" strokeWidth={2.5} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h2 className="text-base font-semibold text-ink-1">开始一场新面试</h2>
                <Badge variant="brand">AI 定制</Badge>
              </div>
              <p className="text-sm text-ink-2 leading-relaxed mb-4">
                选择完整面试（10/15 题）、错题补漏（5 题）或豆包面试大纲。AI 会结合目标岗位与简历定制题目，覆盖技术深度、系统架构、工程实践、沟通表达和算法能力等维度。
              </p>
              <div className="mb-4">
                <ModeOption
                  icon={<MessageSquare className="h-3.5 w-3.5" />}
                  label="文字面试"
                  desc="适合边思考边回答"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <Link to="/interview/mode">
                  <Button variant="primary" leftIcon={<Sparkles className="h-3.5 w-3.5" />} rightIcon={<ArrowRight className="h-3.5 w-3.5" />}>
                    开始新面试
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </Card>

        {/* 错题本 */}
        <Card>
          <CardHeader
            title="错题本"
            description={`${errorQuestions.length} 道薄弱问题`}
            action={
              <Link
                to="/error-book"
                className="text-xs text-brand-600 dark:text-brand-300 hover:underline"
              >
                全部 →
              </Link>
            }
          />
          {errorsLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-4 w-4 animate-spin text-ink-3" />
            </div>
          ) : errorQuestions.length === 0 ? (
            <div className="text-xs text-ink-3 py-4 text-center">暂无错题记录</div>
          ) : (
            <div className="space-y-2">
              {errorQuestions.slice(0, 3).map((eq) => (
                <div
                  key={eq.id}
                  className="p-2.5 rounded-md border border-surface-border dark:border-dark-surface-border hover:border-ink-muted/40 transition-colors cursor-pointer group"
                >
                  <div className="flex items-start gap-2">
                    <div
                      className={cn(
                        'h-1.5 w-1.5 rounded-full flex-shrink-0 mt-1.5',
                        eq.status === 'fresh'
                          ? 'bg-red-500'
                          : eq.status === 'practicing'
                            ? 'bg-amber-500'
                            : 'bg-emerald-500',
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-ink-1 leading-snug line-clamp-2">
                        {eq.question_text}
                      </div>
                      <div className="flex items-center gap-2 mt-1.5 text-2xs text-ink-3">
                        <Badge variant="default" className="!h-4">
                          {eq.dimension}
                        </Badge>
                        <span>错 {eq.frequency} 次</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex flex-col items-stretch gap-3 mb-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="overflow-x-auto">
          <Tabs
            value={tab}
            onChange={setTab}
            items={[
              { key: 'history', label: '历史记录', count: sessions.length },
              { key: 'error', label: '错题本', count: errorQuestions.length },
            ]}
          />
        </div>
        <div className="flex items-center gap-2">
          <div className="relative w-full sm:w-auto">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-muted pointer-events-none" />
            <input
              data-testid="interview-search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索公司或岗位…"
              className="h-8 w-full rounded-md border-0 bg-surface-muted pl-8 pr-3 text-sm text-ink-1 placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/30 sm:w-56 dark:bg-dark-surface-muted"
            />
          </div>
        </div>
      </div>

      {/* 历史记录列表 */}
      {tab === 'history' && (
        <div className="space-y-2">
          {filtered.length === 0 ? (
            <Card>
              {sessions.length === 0 ? (
                <div
                  className="text-center py-8 text-sm text-ink-3"
                  data-testid="interview-history-empty"
                >
                  还没有面试记录，开始你的第一场模拟面试吧
                </div>
              ) : (
                <div
                  className="text-center py-8"
                  data-testid="interview-search-empty"
                >
                  <div className="text-sm font-medium text-ink-1">没有匹配的面试记录</div>
                  <div className="mt-1 text-xs text-ink-3">
                    未找到与
                    <span className="mx-1 font-medium text-ink-1" data-testid="interview-search-empty-query">
                      {search.trim()}
                    </span>
                    匹配的结果
                  </div>
                  <button
                    type="button"
                    data-testid="clear-interview-search"
                    onClick={() => setSearch('')}
                    className="mt-4 inline-flex items-center gap-1.5 rounded-md border border-surface-border px-3 py-1.5 text-xs font-medium text-ink-2 hover:bg-surface-muted hover:text-ink-1 dark:border-dark-surface-border dark:hover:bg-dark-surface-muted"
                  >
                    <X className="h-3.5 w-3.5" />
                    清空搜索
                  </button>
                </div>
              )}
            </Card>
          ) : (
            filtered.map((s) => {
              const displayScore = s.overall_score || s.score || 0
              return (
                <Card
                  key={s.id}
                  hover
                  padding="md"
                  data-testid="session-card"
                  data-session-id={s.id}
                >
                  <div className="flex items-center gap-4">
                    {/* 分数徽章 */}
                    <div
                      className={cn(
                        'h-14 w-14 rounded-md flex flex-col items-center justify-center flex-shrink-0',
                        displayScore >= 90
                          ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                          : displayScore >= 80
                            ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300'
                            : 'bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400',
                      )}
                    >
                      <div className="text-lg font-semibold tabular-nums leading-none">{displayScore}</div>
                      <div className="text-2xs leading-none mt-0.5">分</div>
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-semibold text-ink-1">{s.company || '未知公司'}</span>
                        <span className="text-ink-3">·</span>
                        <span className="text-sm text-ink-2">{s.position || '未知岗位'}</span>
                        {s.status === 'in_progress' && (
                          <Badge variant="brand">进行中</Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-2xs text-ink-3">
                        <span className="flex items-center gap-1">
                          <Calendar className="h-2.5 w-2.5" />
                          {timeAgo(s.created_at)}
                        </span>
                        {s.duration_seconds ? (
                          <span className="flex items-center gap-1">
                            <Clock className="h-2.5 w-2.5" />
                            {formatDuration(s.duration_seconds)}
                          </span>
                        ) : null}
                        <span className="flex items-center gap-1">
                          <MessageSquare className="h-2.5 w-2.5" />
                          {formatInterviewMode(s.mode)}
                        </span>
                        {s.question_count && <span>· {s.question_count} 道题</span>}
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {s.status === 'in_progress' || s.status === 'pending' ? (
                        <Link to={`/interview/${s.id}/live`}>
                          <Button
                            size="sm"
                            variant="primary"
                            leftIcon={<PlayCircle className="h-3.5 w-3.5" />}
                            data-testid={`continue-interview-${s.id}`}
                          >
                            继续面试
                          </Button>
                        </Link>
                      ) : (
                        <Link to={`/interview/${s.id}/report`}>
                          <Button
                            size="sm"
                            variant="ghost"
                            leftIcon={<BarChart3 className="h-3.5 w-3.5" />}
                          >
                            查看报告
                          </Button>
                        </Link>
                      )}
                      <button
                        type="button"
                        aria-label="删除面试"
                        title="删除面试"
                        data-testid={`delete-interview-${s.id}`}
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          setDeleteError(null)
                          setDeleteTarget({
                            id: s.id,
                            label: `${s.company || '未知公司'} · ${s.position || '未知岗位'}`,
                          })
                        }}
                        className="h-8 w-8 rounded-md text-ink-3 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10 dark:hover:text-red-400 transition-colors flex items-center justify-center"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                </Card>
              )
            })
          )}
        </div>
      )}

      {tab === 'error' && (
        <Card>
          {errorsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-ink-3" />
            </div>
          ) : errorQuestions.length === 0 ? (
            <div className="text-center py-8 text-sm text-ink-3">
              暂无错题记录
            </div>
          ) : (
            <div className="divide-y divide-surface-border dark:divide-dark-surface-border">
              {errorQuestions.map((eq) => (
                <div key={eq.id} className="py-3.5 first:pt-0 last:pb-0 flex items-start gap-3 group">
                  <div
                    className={cn(
                      'h-9 w-9 rounded-md flex items-center justify-center flex-shrink-0',
                      eq.status === 'fresh'
                        ? 'bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400'
                        : eq.status === 'practicing'
                          ? 'bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400'
                          : 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
                    )}
                  >
                    <AlertCircle className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-ink-1">{eq.question_text}</span>
                    </div>
                    <div className="flex items-center gap-2 text-2xs text-ink-3">
                      <Badge variant="default">{eq.dimension}</Badge>
                      <span>出现 {eq.frequency} 次</span>
                    </div>
                  </div>
                  <Link to={`/error-book`}>
                    <Button size="sm" variant="secondary" leftIcon={<Lightbulb className="h-3.5 w-3.5" />}>
                      复习
                    </Button>
                  </Link>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* 删除确认对话框 */}
      {deleteTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          data-testid="delete-confirm-dialog"
          onClick={(e) => {
            if (e.target === e.currentTarget && !deleteMutation.isPending) {
              setDeleteError(null)
              setDeleteTarget(null)
            }
          }}
        >
          <div className="w-full max-w-sm rounded-lg bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border shadow-xl p-5">
            <div className="flex items-start gap-3 mb-3">
              <div className="h-9 w-9 rounded-md bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 flex items-center justify-center flex-shrink-0">
                <Trash2 className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-sm font-semibold text-ink-1">删除面试记录</h2>
                <p className="text-xs text-ink-3 mt-1 leading-relaxed">
                  确定要删除「{deleteTarget.label}」吗？此操作会软删除该面试，列表中将不再显示。
                </p>
              </div>
            </div>
            {deleteError && (
              <div
                data-testid="delete-error-message"
                className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs leading-relaxed text-red-600 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-400"
              >
                {deleteError}
              </div>
            )}
            <div className="flex justify-end gap-2 mt-4">
              <Button
                size="sm"
                variant="ghost"
                data-testid="cancel-delete-btn"
                onClick={() => {
                  setDeleteError(null)
                  setDeleteTarget(null)
                }}
                disabled={deleteMutation.isPending}
              >
                取消
              </Button>
              <Button
                size="sm"
                variant="danger"
                data-testid="confirm-delete-btn"
                onClick={async () => {
                  try {
                    setDeleteError(null)
                    await deleteMutation.mutateAsync(deleteTarget.id)
                    setDeleteError(null)
                    setDeleteTarget(null)
                  } catch (err) {
                    const message = err instanceof Error && err.message
                      ? err.message
                      : 'Delete failed. Please retry.'
                    setDeleteError(message)
                  }
                }}
                disabled={deleteMutation.isPending}
                leftIcon={
                  deleteMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" />
                  )
                }
              >
                {deleteMutation.isPending ? '删除中…' : '确认删除'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({
  label,
  value,
  suffix,
  trend,
}: {
  label: string
  value: string
  suffix?: string
  trend: string
}) {
  return (
    <Card className="p-4">
      <div className="text-2xs text-ink-3 mb-1.5">{label}</div>
      <div className="flex items-baseline gap-1">
        <span className="text-2xl font-semibold text-ink-1 tabular-nums tracking-tight">{value}</span>
        {suffix && <span className="text-sm text-ink-3">{suffix}</span>}
      </div>
      <div className="text-2xs text-ink-3 mt-1 flex items-center gap-1">
        {trend}
      </div>
    </Card>
  )
}

function ModeOption({
  icon,
  label,
  desc,
}: {
  icon: React.ReactNode
  label: string
  desc: string
}) {
  return (
    <div className="text-left p-2.5 rounded-md border border-surface-border dark:border-dark-surface-border hover:border-ink-muted/40 hover:bg-surface-muted/50 dark:hover:bg-dark-surface-muted/30 transition-all">
      <div className="flex items-center gap-1.5 mb-0.5 text-ink-1">
        {icon}
        <span className="text-xs font-medium">{label}</span>
      </div>
      <div className="text-2xs text-ink-3">{desc}</div>
    </div>
  )
}
