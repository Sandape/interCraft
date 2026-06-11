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
  Calendar,
  Zap,
  CheckCircle2,
  AlertCircle,
  Activity,
  Clock,
  ArrowRight,
  Lightbulb,
} from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Progress } from '@/components/ui/Progress'
import { Avatar } from '@/components/ui/Avatar'
import {
  dashboardStats,
  upcomingTasks,
  recentActivities,
  resumeBranches,
  interviewHistory,
  growthTrajectory,
  abilityDimensions,
} from '@/data/mockData'
import { formatNumber, timeAgo, truncate } from '@/lib/utils'

export default function Dashboard() {
  const overallAbility = Math.round(
    abilityDimensions.reduce((sum, d) => sum + d.actual, 0) / abilityDimensions.length,
  )
  const lastMonth = growthTrajectory[growthTrajectory.length - 2]
  const thisMonth = growthTrajectory[growthTrajectory.length - 1]
  const abilityGrowth = thisMonth.tech - lastMonth.tech

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto">
      {/* 页面标题区 */}
      <div className="mb-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">早上好，浩然 👋</h1>
            <p className="text-sm text-ink-3 mt-1">
              你已经持续求职
              <span className="text-ink-1 font-medium mx-1">28</span>
              天 · 当前进度良好，建议今天完成 1 场模拟面试
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
          value={dashboardStats.activeBranches}
          suffix={`/ ${dashboardStats.resumeBranches}`}
          change={+1}
          changeLabel="本周新增 1"
        />
        <StatCard
          icon={<MessageSquareText className="h-4 w-4" />}
          label="已完成面试"
          value={dashboardStats.interviewsCompleted}
          suffix="场"
          change={+3}
          changeLabel="本周 +3"
        />
        <StatCard
          icon={<Radar className="h-4 w-4" />}
          label="综合能力"
          value={overallAbility}
          suffix="分"
          change={abilityGrowth}
          changeLabel="本月 +3"
        />
        <StatCard
          icon={<Sparkles className="h-4 w-4" />}
          label="平均面试分"
          value={dashboardStats.averageScore}
          suffix="分"
          change={+2.3}
          changeLabel="对比上月"
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
            description={`${upcomingTasks.length} 项任务 · 1 项高优先级`}
            action={
              <Link
                to="/dashboard"
                className="text-2xs text-ink-3 hover:text-ink-1 transition-colors inline-flex items-center gap-0.5"
              >
                全部 <ChevronRight className="h-3 w-3" />
              </Link>
            }
          />
          <ul className="space-y-2">
            {upcomingTasks.map((t) => (
              <li
                key={t.id}
                className="flex items-start gap-2.5 group cursor-pointer -mx-1.5 px-1.5 py-1.5 rounded hover:bg-surface-muted/60 dark:hover:bg-dark-surface-muted/40 transition-colors"
              >
                <div
                  className={`mt-0.5 h-3.5 w-3.5 rounded border-2 flex-shrink-0 transition-colors ${
                    t.priority === 'high'
                      ? 'border-brand-500 group-hover:bg-brand-500'
                      : 'border-ink-muted group-hover:border-ink-secondary group-hover:bg-ink-secondary'
                  }`}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-ink-1 leading-snug">{t.title}</div>
                  <div className="text-2xs text-ink-3 mt-0.5 flex items-center gap-1.5">
                    <Clock className="h-2.5 w-2.5" />
                    {t.due}
                    {t.priority === 'high' && (
                      <Badge variant="danger" className="ml-1">
                        高优
                      </Badge>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* 简历分支概览 */}
        <Card className="lg:col-span-2">
          <CardHeader
            title="我的简历分支"
            description="每个分支针对特定岗位自动优化"
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
                    b.isMain
                      ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-600 dark:text-brand-300'
                      : 'bg-surface-muted dark:bg-dark-surface-muted text-ink-2 dark:text-dark-ink-secondary'
                  }`}
                >
                  {b.isMain ? <Sparkles className="h-3.5 w-3.5" /> : <Briefcase className="h-3.5 w-3.5" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-ink-1 truncate">{b.name}</div>
                  <div className="text-2xs text-ink-3 mt-0.5 flex items-center gap-2">
                    <span>{timeAgo(b.lastEdited)}</span>
                    <span>·</span>
                    <span>{b.versionCount} 个版本</span>
                  </div>
                </div>
                {!b.isMain && (
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <span className="text-2xs text-ink-3">匹配度</span>
                    <span
                      className={`text-sm font-semibold tabular-nums ${
                        b.matchScore >= 90
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : b.matchScore >= 80
                            ? 'text-brand-600 dark:text-brand-300'
                            : 'text-amber-600 dark:text-amber-400'
                      }`}
                    >
                      {b.matchScore}
                    </span>
                  </div>
                )}
                {b.isMain && (
                  <Badge variant="brand" leftIcon={<Sparkles className="h-2.5 w-2.5" />}>
                    主版
                  </Badge>
                )}
                <ArrowUpRight className="h-3.5 w-3.5 text-ink-muted opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            ))}
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
            {recentActivities.map((a) => (
              <div key={a.id} className="flex gap-2.5 group">
                <div className="flex flex-col items-center flex-shrink-0">
                  <div
                    className={`h-5 w-5 rounded-full flex items-center justify-center ${
                      a.type === 'resume'
                        ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400'
                        : a.type === 'interview'
                          ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                          : 'bg-violet-50 dark:bg-violet-500/10 text-violet-600 dark:text-violet-400'
                    }`}
                  >
                    {a.type === 'resume' ? (
                      <FileText className="h-2.5 w-2.5" />
                    ) : a.type === 'interview' ? (
                      <MessageSquareText className="h-2.5 w-2.5" />
                    ) : (
                      <Radar className="h-2.5 w-2.5" />
                    )}
                  </div>
                  <div className="w-px flex-1 bg-surface-border dark:bg-dark-surface-border mt-1 group-last:hidden" />
                </div>
                <div className="flex-1 min-w-0 pb-3 group-last:pb-0">
                  <div className="text-xs text-ink-1 leading-snug">{a.title}</div>
                  <div className="text-2xs text-ink-3 mt-0.5">{a.detail}</div>
                  <div className="text-2xs text-ink-muted mt-0.5">{a.time}</div>
                </div>
              </div>
            ))}
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
          <Sparkline data={interviewHistory.slice(0, 6).reverse().map((i) => i.score)} />
          <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-surface-border dark:border-dark-surface-border">
            <MiniStat label="最高分" value="92" company="美团" tone="success" />
            <MiniStat label="最低分" value="78" company="小红书" tone="warning" />
            <MiniStat label="通过率" value="100%" company="≥80 分" tone="brand" />
          </div>
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
            to="/profile"
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
            <Link to="/profile" className="text-xs text-brand-600 dark:text-brand-300 hover:underline">
              查看详情 →
            </Link>
          }
        />
        <div className="space-y-3">
          {abilityDimensions.map((d) => (
            <div key={d.key} className="grid grid-cols-12 gap-3 items-center">
              <div className="col-span-3 sm:col-span-2 text-sm font-medium text-ink-1">{d.name}</div>
              <div className="col-span-7 sm:col-span-8">
                <div className="relative">
                  <Progress value={d.actual} size="md" variant="brand" />
                  <div
                    className="absolute top-0 h-1.5 w-px bg-ink-muted"
                    style={{ left: `${d.ideal}%` }}
                    title={`目标 ${d.ideal}`}
                  />
                </div>
              </div>
              <div className="col-span-2 sm:col-span-2 flex items-center justify-end gap-2 text-sm">
                <span className="text-ink-1 font-semibold tabular-nums">{d.actual}</span>
                <span className="text-ink-3 text-2xs">/ {d.ideal}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
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

function Sparkline({ data }: { data: number[] }) {
  const width = 600
  const height = 120
  const padding = 8
  const max = 100
  const min = 60
  const stepX = (width - padding * 2) / (data.length - 1)
  const points = data.map((v, i) => {
    const x = padding + i * stepX
    const y = height - padding - ((v - min) / (max - min)) * (height - padding * 2)
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
        {data.map((_, i) => (
          <span key={i} className="flex-1 text-center">
            {interviewHistory[interviewHistory.length - 1 - i]?.company.slice(0, 2) || ''}
          </span>
        ))}
      </div>
    </div>
  )
}
