import { Link } from 'react-router-dom'
import {
  TrendingUp,
  TrendingDown,
  FileText,
  MessageSquareText,
  Radar,
  Sparkles,
  ArrowUpRight,
  ChevronRight,
  Briefcase,
  Zap,
  Activity,
  Clock,
  ArrowRight,
  Lightbulb,
} from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Progress } from '@/components/ui/Progress'
import { useMemo } from 'react'
import { useResumeBranches } from '@/hooks/queries/useResumeBranches'
import { useAbilities, useDimensionsMeta } from '@/hooks/queries/useAbilities'
import { useTasks } from '@/hooks/queries/useTasks'
import { useActivities } from '@/hooks/queries/useActivities'
import { useInterviewSessions } from '@/hooks/queries/useInterviewSessions'
import { useAuthStore } from '@/stores/useAuthStore'
import { timeAgo } from '@/lib/utils'

export default function Dashboard() {
  const user = useAuthStore((s) => s.user)
  const { data: resumeBranches = [] } = useResumeBranches()
  const { data: abilitiesData } = useAbilities()
  const { data: dimensionsMeta } = useDimensionsMeta()
  const { data: tasksData } = useTasks({ limit: 5 })
  const { data: activitiesData } = useActivities(undefined, 5)
  const { data: interviewSessionsData } = useInterviewSessions({ limit: 6 })

  const abilities = (abilitiesData as any)?.data ?? []
  const dimLabels = (dimensionsMeta as any)?.dimensions ?? []
  const tasks = (tasksData as any)?.data ?? []
  const activities = (activitiesData as any)?.items ?? []
  const sessions = (interviewSessionsData as any)?.data ?? []

  // ---- derived stats ----
  const completedSessions = useMemo(
    () => sessions.filter((s: any) => s.status === 'completed'),
    [sessions],
  )
  const interviewsCompleted = completedSessions.length
  const averageScore = useMemo(() => {
    const scores = completedSessions
      .map((s: any) => s.overall_score ?? s.score)
      .filter((v: unknown) => typeof v === 'number' && v > 0) as number[]
    if (scores.length === 0) return 0
    return Math.round(scores.reduce((a: number, b: number) => a + b, 0) / scores.length * 10) / 10
  }, [completedSessions])

  const abilityByName = useMemo(() => {
    const map = new Map<string, string>()
    for (const d of dimLabels) {
      map.set(d.key, d.label_zh)
    }
    return map
  }, [dimLabels])

  const overallAbility = useMemo(() => {
    if (abilities.length === 0) return 0
    const sum = abilities.reduce((acc: number, d: any) => acc + Number(d.actual_score ?? 0), 0)
    return Math.round((sum / abilities.length) * 10) / 10
  }, [abilities])

  const abilityGrowth = useMemo(() => {
    if (abilities.length === 0) return 0
    return abilities.filter((d: any) => (d.actual_score ?? 0) > 0).length > 0 ? 0 : 0
    // Growth is computed via history API; show 0 as placeholder
  }, [abilities])

  const activeCount = resumeBranches.filter((b) => b.status !== 'archived').length

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto">
      {/* 页面标题区 */}
      <div className="mb-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">
              {getGreeting()}，{user?.display_name || '用户'} 👋
            </h1>
            <p className="text-sm text-ink-3 mt-1">
              {interviewsCompleted > 0
                ? `你已完成 ${interviewsCompleted} 场模拟面试 · 综合能力 ${overallAbility} 分`
                : '开始你的第一场模拟面试，获取能力画像'}
            </p>
          </div>
          <div className="hidden md:flex items-center gap-2">
            <Link to="/interview/new">
              <Button variant="primary" leftIcon={<Zap className="h-3.5 w-3.5" />}>
                开始模拟面试
              </Button>
            </Link>
            <Link to="/resume">
              <Button variant="secondary" leftIcon={<FileText className="h-3.5 w-3.5" />}>
                管理简历
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* 关键指标卡 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard
          icon={<FileText className="h-4 w-4" />}
          label="活跃简历"
          value={activeCount}
          suffix={`/ ${resumeBranches.length}`}
          change={resumeBranches.length > 0 ? +1 : 0}
          changeLabel={resumeBranches.length > 0 ? `${resumeBranches.length} 个分支` : '暂无'}
        />
        <StatCard
          icon={<MessageSquareText className="h-4 w-4" />}
          label="已完成面试"
          value={interviewsCompleted}
          suffix="场"
          change={interviewsCompleted > 0 ? interviewsCompleted : 0}
          changeLabel={interviewsCompleted > 0 ? `共 ${interviewsCompleted} 场` : '暂无数据'}
        />
        <StatCard
          icon={<Radar className="h-4 w-4" />}
          label="综合能力"
          value={overallAbility}
          suffix="/ 10"
          change={abilityGrowth}
          changeLabel={overallAbility > 0 ? `${abilities.length} 个维度` : '完成面试后生成'}
        />
        <StatCard
          icon={<Sparkles className="h-4 w-4" />}
          label="平均面试分"
          value={averageScore}
          suffix="分"
          change={averageScore > 0 ? 0 : 0}
          changeLabel={averageScore > 0 ? `${completedSessions.length} 场面试` : '暂无数据'}
          isFloat
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* AI 建议 - 占据 2 列 */}
        <Card className="lg:col-span-2 p-5">
          <div className="flex items-start gap-3">
            <div className="h-8 w-8 rounded-md bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center flex-shrink-0">
              <Sparkles className="h-4 w-4 text-white" strokeWidth={2.5} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-sm font-semibold text-ink-1">AI 智能建议</h3>
                <Badge variant="brand">实时</Badge>
              </div>
              <p className="text-sm text-ink-2 leading-relaxed">
                检测到「系统设计」维度本周模拟面试中失分 3 次，建议今天先完成
                <span className="text-ink-1 font-medium"> 1 套 L4 系统设计专项题库</span>
                。结合你正在优化的「字节跳动」简历分支，预计可将面试综合分提升
                <span className="text-emerald-600 dark:text-emerald-400 font-medium"> 4-6 分</span>。
              </p>
              <div className="flex flex-wrap gap-2 mt-3">
                <Button size="sm" variant="primary" rightIcon={<ArrowRight className="h-3 w-3" />}>
                  立即开始练习
                </Button>
                <Button size="sm" variant="ghost">
                  查看能力报告
                </Button>
              </div>
            </div>
          </div>
        </Card>

        {/* 今日待办 */}
        <Card className="p-5">
          <CardHeader
            title="今日待办"
            description={`${tasks.length} 项任务`}
            action={
              <Link
                to="/dashboard"
                className="text-2xs text-ink-3 hover:text-ink-1 transition-colors inline-flex items-center gap-0.5"
              >
                全部 <ChevronRight className="h-3 w-3" />
              </Link>
            }
          />
          {tasks.length > 0 ? (
            <ul className="space-y-2">
              {tasks.slice(0, 5).map((t: any) => (
                <li
                  key={t.id}
                  className="flex items-start gap-2.5 group cursor-pointer -mx-1.5 px-1.5 py-1.5 rounded hover:bg-surface-muted/60 dark:hover:bg-dark-surface-muted/40 transition-colors"
                >
                  <div
                    className={`mt-0.5 h-3.5 w-3.5 rounded border-2 flex-shrink-0 transition-colors ${
                      t.status === 'pending'
                        ? 'border-brand-500 group-hover:bg-brand-500'
                        : 'border-ink-muted group-hover:border-ink-secondary group-hover:bg-ink-secondary'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-ink-1 leading-snug">{t.title}</div>
                    <div className="text-2xs text-ink-3 mt-0.5 flex items-center gap-1.5">
                      <Clock className="h-2.5 w-2.5" />
                      {timeAgo(t.created_at)}
                      {t.status === 'pending' && (
                        <Badge variant="warning" className="ml-1">
                          待办
                        </Badge>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-3 py-3 text-center">暂无待办任务</p>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* 简历分支概览 */}
        <Card className="lg:col-span-2">
          <CardHeader
            title="我的简历分支"
            description={`${activeCount} 个活跃 · ${resumeBranches.length} 个总计`}
            action={
              <Link to="/resume" className="text-xs text-brand-600 dark:text-brand-300 hover:underline">
                管理 →
              </Link>
            }
          />
          <div className="space-y-1.5">
            {resumeBranches.slice(0, 5).map((b) => (
              <Link
                key={b.id}
                to={`/resume/${b.id}`}
                className="flex items-center gap-3 px-2 py-2 -mx-2 rounded hover:bg-surface-muted/60 dark:hover:bg-dark-surface-muted/40 transition-colors group"
              >
                <div
                  className={`h-8 w-8 rounded-md flex items-center justify-center flex-shrink-0 ${
                    b.is_main
                      ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-600 dark:text-brand-300'
                      : 'bg-surface-muted dark:bg-dark-surface-muted text-ink-2 dark:text-dark-ink-secondary'
                  }`}
                >
                  {b.is_main ? <Sparkles className="h-3.5 w-3.5" /> : <Briefcase className="h-3.5 w-3.5" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-ink-1 truncate">{b.name}</div>
                  <div className="text-2xs text-ink-3 mt-0.5 flex items-center gap-2">
                    <span>{timeAgo(b.last_edited_at)}</span>
                    <span>·</span>
                    <span>{b.version_count} 个版本</span>
                  </div>
                </div>
                {!b.is_main && (
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <span className="text-2xs text-ink-3">匹配度</span>
                    <span
                      className={`text-sm font-semibold tabular-nums ${
                        (b.match_score ?? 0) >= 90
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : (b.match_score ?? 0) >= 80
                            ? 'text-brand-600 dark:text-brand-300'
                            : 'text-amber-600 dark:text-amber-400'
                      }`}
                    >
                      {b.match_score ?? '—'}
                    </span>
                  </div>
                )}
                {b.is_main && (
                  <Badge variant="brand" leftIcon={<Sparkles className="h-2.5 w-2.5" />}>
                    主版
                  </Badge>
                )}
                <ArrowUpRight className="h-3.5 w-3.5 text-ink-muted opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            ))}
            {resumeBranches.length === 0 && (
              <p className="text-sm text-ink-3 py-3 text-center">暂无简历，去「简历中心」创建第一份</p>
            )}
          </div>
        </Card>

        {/* 活动时间线 */}
        <Card>
          <CardHeader
            title="最近活动"
            description="平台内的关键事件"
            action={<Activity className="h-3.5 w-3.5 text-ink-3" />}
          />
          <div className="space-y-3">
            {activities.length > 0 ? (
              activities.slice(0, 5).map((a: any) => {
                const info = getActivityDisplay(a)
                return (
                  <div key={a.id} className="flex gap-2.5 group">
                    <div className="flex flex-col items-center flex-shrink-0">
                      <div
                        className={`h-5 w-5 rounded-full flex items-center justify-center ${
                          info.icon === 'resume'
                            ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400'
                            : info.icon === 'interview'
                              ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                              : 'bg-violet-50 dark:bg-violet-500/10 text-violet-600 dark:text-violet-400'
                        }`}
                      >
                        {info.icon === 'resume' ? (
                          <FileText className="h-2.5 w-2.5" />
                        ) : info.icon === 'interview' ? (
                          <MessageSquareText className="h-2.5 w-2.5" />
                        ) : (
                          <Radar className="h-2.5 w-2.5" />
                        )}
                      </div>
                      <div className="w-px flex-1 bg-surface-border dark:bg-dark-surface-border mt-1 group-last:hidden" />
                    </div>
                    <div className="flex-1 min-w-0 pb-3 group-last:pb-0">
                      <div className="text-xs text-ink-1 leading-snug">{info.title}</div>
                      <div className="text-2xs text-ink-3 mt-0.5">{info.detail}</div>
                      <div className="text-2xs text-ink-muted mt-0.5">{timeAgo(a.occurred_at)}</div>
                    </div>
                  </div>
                )
              })
            ) : (
              <p className="text-sm text-ink-3 py-3 text-center">暂无活动记录</p>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* 面试战绩 */}
        <Card className="lg:col-span-2">
          <CardHeader
            title="面试表现趋势"
            description="近 6 场模拟面试 · 综合评分"
            action={
              <Link
                to="/interview"
                className="text-xs text-brand-600 dark:text-brand-300 hover:underline"
              >
                查看全部 →
              </Link>
            }
          />
          {completedSessions.length > 0 ? (
            <>
              <Sparkline
                data={[...completedSessions].reverse().map((s: any) => s.overall_score ?? s.score ?? 0)}
                labels={[...completedSessions].reverse().map((s: any) => (s.company || '').slice(0, 2))}
              />
              <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-surface-border dark:border-dark-surface-border">
                <MiniStat
                  label="最高分"
                  value={String(Math.max(...completedSessions.map((s: any) => s.overall_score ?? s.score ?? 0)))}
                  company={(() => {
                    const best = [...completedSessions].sort((a: any, b: any) => (b.overall_score ?? b.score ?? 0) - (a.overall_score ?? a.score ?? 0))[0]
                    return best?.company || ''
                  })()}
                  tone="success"
                />
                <MiniStat
                  label="最低分"
                  value={String(Math.min(...completedSessions.map((s: any) => s.overall_score ?? s.score ?? 0)))}
                  company={(() => {
                    const worst = [...completedSessions].sort((a: any, b: any) => (a.overall_score ?? a.score ?? 0) - (b.overall_score ?? b.score ?? 0))[0]
                    return worst?.company || ''
                  })()}
                  tone="warning"
                />
                <MiniStat
                  label="通过率"
                  value={`${Math.round(completedSessions.filter((s: any) => (s.overall_score ?? s.score ?? 0) >= 80).length / completedSessions.length * 100)}%`}
                  company="≥80 分"
                  tone="brand"
                />
              </div>
            </>
          ) : (
            <p className="text-sm text-ink-3 py-8 text-center">完成模拟面试后显示趋势图</p>
          )}
        </Card>

        {/* 个性化建议 */}
        <Card>
          <CardHeader
            title="提升建议"
            description="基于能力画像生成"
            action={<Lightbulb className="h-3.5 w-3.5 text-ink-3" />}
          />
          <div className="space-y-2.5">
            <SuggestionItem
              title="系统设计强化"
              impact="+13 分"
              time="2 周"
              priority="high"
            />
            <SuggestionItem
              title="业务理解补充"
              impact="+15 分"
              time="1 周"
              priority="high"
            />
            <SuggestionItem
              title="错题本复习"
              impact="+5 分"
              time="3 天"
              priority="medium"
            />
          </div>
          <Link
            to="/ability-profile"
            className="block mt-3 pt-3 border-t border-surface-border dark:border-dark-surface-border text-xs text-brand-600 dark:text-brand-300 hover:underline text-center"
          >
            查看完整画像 →
          </Link>
        </Card>
      </div>

      {/* 能力概览 - 全宽 */}
      <Card className="mb-6">
        <CardHeader
          title="能力概览"
          description="6 个核心维度的实际得分"
          action={
            <Link to="/ability-profile" className="text-xs text-brand-600 dark:text-brand-300 hover:underline">
              查看详情 →
            </Link>
          }
        />
        <div className="space-y-3">
          {abilities.length > 0 ? (
            abilities.map((d: any) => {
              const name = abilityByName.get(d.dimension_key) || d.dimension_key
              const actual = d.actual_score ?? 0
              const ideal = d.ideal_score ?? 100
              return (
                <div key={d.id || d.dimension_key} className="grid grid-cols-12 gap-3 items-center">
                  <div className="col-span-3 sm:col-span-2 text-sm font-medium text-ink-1">{name}</div>
                  <div className="col-span-7 sm:col-span-8">
                    <div className="relative">
                      <Progress value={actual} size="md" variant="brand" />
                      <div
                        className="absolute top-0 h-1.5 w-px bg-ink-muted"
                        style={{ left: `${Math.min(ideal, 100)}%` }}
                        title={`目标 ${ideal}`}
                      />
                    </div>
                  </div>
                  <div className="col-span-2 sm:col-span-2 flex items-center justify-end gap-2 text-sm">
                    <span className="text-ink-1 font-semibold tabular-nums">{actual}</span>
                    <span className="text-ink-3 text-2xs">/ {ideal}</span>
                  </div>
                </div>
              )
            })
          ) : (
            <p className="text-sm text-ink-3 py-3 text-center">完成模拟面试后生成能力数据</p>
          )}
        </div>
      </Card>
    </div>
  )
}

function getGreeting(): string {
  const h = new Date().getHours()
  if (h < 12) return '早上好'
  if (h < 18) return '下午好'
  return '晚上好'
}

function getActivityDisplay(a: any): { title: string; detail: string; icon: string } {
  const type = a.type || ''
  const payload = a.payload_json || {}
  if (type.includes('resume') || payload.branch_name) {
    return {
      title: payload.summary || '简历更新',
      detail: payload.branch_name || '',
      icon: 'resume',
    }
  }
  if (type.includes('interview') || type.includes('session')) {
    return {
      title: payload.summary || '面试记录',
      detail: [payload.company, payload.position].filter(Boolean).join(' · ') || '',
      icon: 'interview',
    }
  }
  return {
    title: payload.summary || type || '系统事件',
    detail: payload.detail || '',
    icon: 'ability',
  }
}

function StatCard({
  icon,
  label,
  value,
  suffix,
  change,
  changeLabel,
  isFloat,
}: {
  icon: React.ReactNode
  label: string
  value: number
  suffix?: string
  change: number
  changeLabel: string
  isFloat?: boolean
}) {
  const positive = change > 0
  const display = isFloat ? value.toFixed(1) : value
  return (
    <Card className="p-4 hover:shadow-notion transition-shadow">
      <div className="flex items-start justify-between mb-2.5">
        <div className="h-7 w-7 rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-2 dark:text-dark-ink-secondary flex items-center justify-center">
          {icon}
        </div>
        {change !== 0 && (
          <Badge variant={positive ? 'success' : 'danger'} className="!h-5">
            {positive ? <TrendingUp className="h-2.5 w-2.5" /> : <TrendingDown className="h-2.5 w-2.5" />}
            {positive ? '+' : ''}
            {change}
            {isFloat ? '' : ''}
          </Badge>
        )}
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-2xl font-semibold text-ink-1 tabular-nums tracking-tight">{display}</span>
        {suffix && <span className="text-sm text-ink-3">{suffix}</span>}
      </div>
      <div className="text-2xs text-ink-3 mt-1">{label}</div>
      <div className="text-2xs text-ink-muted mt-0.5">{changeLabel}</div>
    </Card>
  )
}

function MiniStat({
  label,
  value,
  company,
  tone,
}: {
  label: string
  value: string
  company: string
  tone: 'success' | 'warning' | 'brand'
}) {
  const colorMap = {
    success: 'text-emerald-600 dark:text-emerald-400',
    warning: 'text-amber-600 dark:text-amber-400',
    brand: 'text-brand-600 dark:text-brand-300',
  }
  return (
    <div>
      <div className="text-2xs text-ink-3">{label}</div>
      <div className="flex items-baseline gap-1.5 mt-0.5">
        <span className={`text-xl font-semibold tabular-nums ${colorMap[tone]}`}>{value}</span>
        <span className="text-2xs text-ink-3 truncate">{company}</span>
      </div>
    </div>
  )
}

function SuggestionItem({
  title,
  impact,
  time,
  priority,
}: {
  title: string
  impact: string
  time: string
  priority: 'high' | 'medium' | 'low'
}) {
  return (
    <div className="flex items-center gap-2.5 group cursor-pointer -mx-1.5 px-1.5 py-1.5 rounded hover:bg-surface-muted/60 dark:hover:bg-dark-surface-muted/40 transition-colors">
      <div
        className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${
          priority === 'high' ? 'bg-red-500' : priority === 'medium' ? 'bg-amber-500' : 'bg-emerald-500'
        }`}
      />
      <div className="flex-1 min-w-0">
        <div className="text-xs text-ink-1 truncate">{title}</div>
        <div className="text-2xs text-ink-3 mt-0.5 flex items-center gap-1.5">
          <span>预计提升 {impact}</span>
          <span>·</span>
          <span>{time}</span>
        </div>
      </div>
      <ChevronRight className="h-3.5 w-3.5 text-ink-muted opacity-0 group-hover:opacity-100 transition-opacity" />
    </div>
  )
}

function Sparkline({ data, labels }: { data: number[]; labels?: string[] }) {
  if (data.length === 0) return <p className="text-sm text-ink-3 py-8 text-center">暂无数据</p>
  const width = 600
  const height = 120
  const padding = 8
  const max = Math.max(...data, 10)
  const min = Math.min(...data, 0)
  const range = max - min || 1
  const stepX = (width - padding * 2) / Math.max(data.length - 1, 1)
  const points = data.map((v, i) => {
    const x = padding + i * stepX
    const y = height - padding - ((v - min) / range) * (height - padding * 2)
    return [x, y]
  })
  const linePath = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'} ${x} ${y}`).join(' ')
  const areaPath = `${linePath} L ${points[points.length - 1][0]} ${height - padding} L ${points[0][0]} ${height - padding} Z`
  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-32" preserveAspectRatio="none">
        <defs>
          <linearGradient id="sparkline-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(59, 130, 246)" stopOpacity="0.18" />
            <stop offset="100%" stopColor="rgb(59, 130, 246)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((p) => (
          <line
            key={p}
            x1={padding}
            x2={width - padding}
            y1={padding + (height - padding * 2) * p}
            y2={padding + (height - padding * 2) * p}
            stroke="currentColor"
            strokeOpacity="0.06"
            strokeDasharray="2 3"
          />
        ))}
        <path d={areaPath} fill="url(#sparkline-grad)" />
        <path d={linePath} fill="none" stroke="rgb(59, 130, 246)" strokeWidth="2" strokeLinejoin="round" />
        {points.map(([x, y], i) => (
          <g key={i}>
            <circle cx={x} cy={y} r="3" fill="white" stroke="rgb(59, 130, 246)" strokeWidth="2" />
          </g>
        ))}
        {points.map(([x, y], i) => (
          <text
            key={i}
            x={x}
            y={y - 8}
            textAnchor="middle"
            className="fill-current text-2xs"
            style={{ fontSize: 10 }}
          >
            {data[i]}
          </text>
        ))}
      </svg>
      <div className="flex items-center justify-between mt-2 text-2xs text-ink-3">
        {(labels ?? data.map(() => '')).map((label, i) => (
          <span key={i} className="flex-1 text-center">
            {label}
          </span>
        ))}
      </div>
    </div>
  )
}
