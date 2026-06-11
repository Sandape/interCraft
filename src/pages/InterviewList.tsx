import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Plus,
  Search,
  Filter,
  Mic,
  MessageSquare,
  ChevronRight,
  Sparkles,
  Calendar,
  Clock,
  TrendingUp,
  TrendingDown,
  BarChart3,
  History,
  AlertCircle,
  BookOpen,
  ArrowRight,
  CheckCircle2,
  XCircle,
  Lightbulb,
} from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Tabs } from '@/components/ui/Tabs'
import { Progress } from '@/components/ui/Progress'
import { interviewHistory, errorBook } from '@/data/mockData'
import { formatDuration, timeAgo, cn } from '@/lib/utils'

export default function InterviewList() {
  const [tab, setTab] = useState('history')
  const [search, setSearch] = useState('')

  const filtered = interviewHistory.filter((i) =>
    i.company.toLowerCase().includes(search.toLowerCase()) ||
    i.position.toLowerCase().includes(search.toLowerCase()),
  )

  const avgScore = Math.round(
    interviewHistory.reduce((sum, i) => sum + i.score, 0) / interviewHistory.length,
  )
  const passRate = Math.round(
    (interviewHistory.filter((i) => i.score >= 80).length / interviewHistory.length) * 100,
  )
  const totalHours = Math.round(
    interviewHistory.reduce((sum, i) => sum + i.duration, 0) / 3600,
  )

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto">
      {/* 页头 */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">模拟面试</h1>
          <p className="text-sm text-ink-3 mt-1">
            基于简历和目标岗位生成定制化面试题库，AI 全程实时反馈
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/interview/new">
            <Button variant="primary" leftIcon={<Plus className="h-3.5 w-3.5" />}>
              开始新面试
            </Button>
          </Link>
        </div>
      </div>

      {/* 关键指标 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard
          label="累计面试"
          value={interviewHistory.length.toString()}
          suffix="场"
          trend="+3 本周"
          trendUp
        />
        <StatCard
          label="平均评分"
          value={avgScore.toString()}
          suffix="分"
          trend="+2.3 对比上月"
          trendUp
        />
        <StatCard
          label="通过率"
          value={passRate.toString()}
          suffix="%"
          trend="≥80 分"
        />
        <StatCard
          label="练习时长"
          value={totalHours.toString()}
          suffix="小时"
          trend="累计"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* 开始新面试 Hero */}
        <Card className="lg:col-span-2 p-6 bg-gradient-to-br from-brand-50/60 via-surface to-surface dark:from-brand-500/5 dark:via-dark-surface dark:to-dark-surface border-brand-200/60 dark:border-brand-500/20">
          <div className="flex items-start gap-5">
            <div className="h-14 w-14 rounded-lg bg-gradient-to-br from-brand-900 to-brand-600 dark:from-brand-500 dark:to-brand-300 flex items-center justify-center flex-shrink-0 shadow-notion">
              <Sparkles className="h-6 w-6 text-white" strokeWidth={2.5} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h2 className="text-base font-semibold text-ink-1">开始一场新面试</h2>
                <Badge variant="brand">AI 定制</Badge>
              </div>
              <p className="text-sm text-ink-2 leading-relaxed mb-4">
                AI 将基于你的简历和目标岗位自动生成
                <span className="text-ink-1 font-medium mx-1">8-10</span>
                道结构化问题，覆盖技术深度、系统设计、工程实践、算法和软素质 5 个维度。
              </p>
              <div className="grid grid-cols-3 gap-2 mb-4">
                <ModeOption
                  icon={<MessageSquare className="h-3.5 w-3.5" />}
                  label="文字面试"
                  desc="适合边思考边回答"
                />
                <ModeOption
                  icon={<Mic className="h-3.5 w-3.5" />}
                  label="语音面试"
                  desc="更接近真实场景"
                  recommended
                />
                <ModeOption
                  icon={<BarChart3 className="h-3.5 w-3.5" />}
                  label="专项训练"
                  desc="聚焦单一维度"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <Link to="/interview/new">
                  <Button variant="primary" leftIcon={<Sparkles className="h-3.5 w-3.5" />} rightIcon={<ArrowRight className="h-3.5 w-3.5" />}>
                    一键开始（基于「字节跳动」简历）
                  </Button>
                </Link>
                <Button variant="secondary" leftIcon={<Calendar className="h-3.5 w-3.5" />}>
                  自定义设置
                </Button>
              </div>
            </div>
          </div>
        </Card>

        {/* 错题本 */}
        <Card>
          <CardHeader
            title="错题本"
            description={`${errorBook.length} 道薄弱问题`}
            action={
              <Link
                to="/interview"
                className="text-xs text-brand-600 dark:text-brand-300 hover:underline"
              >
                全部 →
              </Link>
            }
          />
          <div className="space-y-2">
            {errorBook.slice(0, 3).map((eq) => (
              <div
                key={eq.id}
                className="p-2.5 rounded-md border border-surface-border dark:border-dark-surface-border hover:border-ink-muted/40 transition-colors cursor-pointer group"
              >
                <div className="flex items-start gap-2">
                  <div
                    className={cn(
                      'h-1.5 w-1.5 rounded-full flex-shrink-0 mt-1.5',
                      eq.difficulty === 'hard'
                        ? 'bg-red-500'
                        : eq.difficulty === 'medium'
                          ? 'bg-amber-500'
                          : 'bg-emerald-500',
                    )}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-ink-1 leading-snug line-clamp-2">
                      {eq.question}
                    </div>
                    <div className="flex items-center gap-2 mt-1.5 text-2xs text-ink-3">
                      <Badge variant="default" className="!h-4">
                        {eq.category}
                      </Badge>
                      <span>错 {eq.frequency} 次</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <Link
            to="/interview"
            className="mt-3 pt-3 border-t border-surface-border dark:border-dark-surface-border block text-xs text-center text-brand-600 dark:text-brand-300 hover:underline"
          >
            查看全部错题 →
          </Link>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex items-center justify-between gap-3 mb-4">
        <Tabs
          value={tab}
          onChange={setTab}
          items={[
            { key: 'history', label: '历史记录', count: interviewHistory.length },
            { key: 'bookmarks', label: '收藏', count: 3 },
            { key: 'error', label: '错题本', count: errorBook.length },
          ]}
        />
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-muted pointer-events-none" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索公司或岗位…"
              className="h-8 pl-8 pr-3 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border-0 focus:outline-none focus:ring-2 focus:ring-brand-500/30 w-56"
            />
          </div>
          <Button size="md" variant="ghost" leftIcon={<Filter className="h-3.5 w-3.5" />}>
            筛选
          </Button>
        </div>
      </div>

      {/* 历史记录列表 */}
      {tab === 'history' && (
        <div className="space-y-2">
          {filtered.map((i) => (
            <Card key={i.id} hover padding="md">
              <div className="flex items-center gap-4">
                {/* 分数徽章 */}
                <div
                  className={cn(
                    'h-14 w-14 rounded-md flex flex-col items-center justify-center flex-shrink-0',
                    i.score >= 90
                      ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                      : i.score >= 80
                        ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300'
                        : 'bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400',
                  )}
                >
                  <div className="text-lg font-semibold tabular-nums leading-none">{i.score}</div>
                  <div className="text-2xs leading-none mt-0.5">分</div>
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-semibold text-ink-1">{i.company}</span>
                    <span className="text-ink-3">·</span>
                    <span className="text-sm text-ink-2">{i.position}</span>
                  </div>
                  <div className="flex items-center gap-3 text-2xs text-ink-3">
                    <span className="flex items-center gap-1">
                      <Calendar className="h-2.5 w-2.5" />
                      {timeAgo(i.date)}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="h-2.5 w-2.5" />
                      {formatDuration(i.duration)}
                    </span>
                    <span className="flex items-center gap-1">
                      {i.mode === 'voice' ? <Mic className="h-2.5 w-2.5" /> : <MessageSquare className="h-2.5 w-2.5" />}
                      {i.mode === 'voice' ? '语音' : '文字'}
                    </span>
                    <span>· {i.questions} 道题</span>
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    {i.dimensions.slice(0, 5).map((d) => (
                      <div key={d.name} className="flex items-center gap-1 text-2xs">
                        <span className="text-ink-3">{d.name}</span>
                        <span
                          className={cn(
                            'font-semibold tabular-nums',
                            d.score >= 85
                              ? 'text-emerald-600 dark:text-emerald-400'
                              : d.score >= 75
                                ? 'text-brand-600 dark:text-brand-300'
                                : 'text-amber-600 dark:text-amber-400',
                          )}
                        >
                          {d.score}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <Button size="sm" variant="ghost" leftIcon={<BarChart3 className="h-3.5 w-3.5" />}>
                    查看报告
                  </Button>
                  <Button size="sm" variant="secondary" rightIcon={<ChevronRight className="h-3.5 w-3.5" />}>
                    复盘
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {tab === 'error' && (
        <Card>
          <div className="divide-y divide-surface-border dark:divide-dark-surface-border">
            {errorBook.map((eq) => (
              <div key={eq.id} className="py-3.5 first:pt-0 last:pb-0 flex items-start gap-3 group">
                <div
                  className={cn(
                    'h-9 w-9 rounded-md flex items-center justify-center flex-shrink-0',
                    eq.difficulty === 'hard'
                      ? 'bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400'
                      : eq.difficulty === 'medium'
                        ? 'bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400'
                        : 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
                  )}
                >
                  {eq.difficulty === 'hard' ? (
                    <XCircle className="h-4 w-4" />
                  ) : eq.difficulty === 'medium' ? (
                    <AlertCircle className="h-4 w-4" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-ink-1">{eq.question}</span>
                  </div>
                  <div className="text-xs text-ink-2 leading-relaxed mb-2">{eq.hint}</div>
                  <div className="flex items-center gap-2 text-2xs text-ink-3">
                    <Badge variant="default">{eq.category}</Badge>
                    <span>出现 {eq.frequency} 次</span>
                    <span>·</span>
                    <span>最近 {timeAgo(eq.lastMissed)}</span>
                  </div>
                </div>
                <Button size="sm" variant="secondary" leftIcon={<Lightbulb className="h-3.5 w-3.5" />}>
                  复习
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

function StatCard({
  label,
  value,
  suffix,
  trend,
  trendUp,
}: {
  label: string
  value: string
  suffix?: string
  trend: string
  trendUp?: boolean
}) {
  return (
    <Card className="p-4">
      <div className="text-2xs text-ink-3 mb-1.5">{label}</div>
      <div className="flex items-baseline gap-1">
        <span className="text-2xl font-semibold text-ink-1 tabular-nums tracking-tight">{value}</span>
        {suffix && <span className="text-sm text-ink-3">{suffix}</span>}
      </div>
      {trend && (
        <div className="text-2xs text-ink-3 mt-1 flex items-center gap-1">
          {trendUp !== undefined &&
            (trendUp ? (
              <TrendingUp className="h-2.5 w-2.5 text-emerald-500" />
            ) : (
              <TrendingDown className="h-2.5 w-2.5 text-red-500" />
            ))}
          {trend}
        </div>
      )}
    </Card>
  )
}

function ModeOption({
  icon,
  label,
  desc,
  recommended,
}: {
  icon: React.ReactNode
  label: string
  desc: string
  recommended?: boolean
}) {
  return (
    <button className="relative text-left p-2.5 rounded-md border border-surface-border dark:border-dark-surface-border hover:border-ink-muted/40 hover:bg-surface-muted/50 dark:hover:bg-dark-surface-muted/30 transition-all">
      {recommended && (
        <div className="absolute -top-1.5 -right-1.5">
          <Badge variant="brand" className="!h-4">
            推荐
          </Badge>
        </div>
      )}
      <div className="flex items-center gap-1.5 mb-0.5 text-ink-1">
        {icon}
        <span className="text-xs font-medium">{label}</span>
      </div>
      <div className="text-2xs text-ink-3">{desc}</div>
    </button>
  )
}
