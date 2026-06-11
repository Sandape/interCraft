import { useState } from 'react'
import {
  Radar as RadarIcon,
  Download,
  Share2,
  TrendingUp,
  TrendingDown,
  Target,
  Sparkles,
  ArrowRight,
  Calendar,
  ChevronDown,
  AlertCircle,
  CheckCircle2,
  Lightbulb,
  ExternalLink,
  Clock,
  BookOpen,
  Zap,
  FileText,
  MessageSquare,
  BarChart3,
  Star,
} from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Progress } from '@/components/ui/Progress'
import { Tabs } from '@/components/ui/Tabs'
import { abilityDimensions, growthTrajectory, improvementSuggestions } from '@/data/mockData'
import { cn } from '@/lib/utils'

export default function Profile() {
  const [activeDim, setActiveDim] = useState<string | null>(null)
  const [timeRange, setTimeRange] = useState('6m')
  const [tab, setTab] = useState('overview')

  const overallIdeal = Math.round(
    abilityDimensions.reduce((sum, d) => sum + d.ideal, 0) / abilityDimensions.length,
  )
  const overallActual = Math.round(
    abilityDimensions.reduce((sum, d) => sum + d.actual, 0) / abilityDimensions.length,
  )
  const gap = overallIdeal - overallActual
  const lastMonth = growthTrajectory[growthTrajectory.length - 2]
  const thisMonth = growthTrajectory[growthTrajectory.length - 1]
  const growth = Math.round(
    (thisMonth.tech + thisMonth.arch + thisMonth.eng + thisMonth.comm + thisMonth.algo + thisMonth.biz) / 6 -
      (lastMonth.tech + lastMonth.arch + lastMonth.eng + lastMonth.comm + lastMonth.algo + lastMonth.biz) / 6,
  )

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto">
      {/* 页头 */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">个人能力画像</h1>
          <p className="text-sm text-ink-3 mt-1">
            对比理想与真实能力，量化差距，AI 生成针对性提升路径
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" leftIcon={<Share2 className="h-3.5 w-3.5" />}>
            分享给导师
          </Button>
          <Button variant="primary" leftIcon={<Download className="h-3.5 w-3.5" />}>
            导出报告
          </Button>
        </div>
      </div>

      {/* 总览指标 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <Card className="p-4">
          <div className="text-2xs text-ink-3 mb-1.5">综合能力</div>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-semibold text-ink-1 tabular-nums tracking-tight">
              {overallActual}
            </span>
            <span className="text-sm text-ink-3">/ {overallIdeal}</span>
          </div>
          <div className="text-2xs text-amber-600 dark:text-amber-400 mt-1 flex items-center gap-1">
            <Target className="h-2.5 w-2.5" />
            距目标差 {gap} 分
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-2xs text-ink-3 mb-1.5">本月成长</div>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-semibold text-ink-1 tabular-nums tracking-tight">+{growth}</span>
            <span className="text-sm text-ink-3">分</span>
          </div>
          <div className="text-2xs text-emerald-600 dark:text-emerald-400 mt-1 flex items-center gap-1">
            <TrendingUp className="h-2.5 w-2.5" />
            对比上月
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-2xs text-ink-3 mb-1.5">最强维度</div>
          <div className="text-2xl font-semibold text-ink-1 tracking-tight">工程实践</div>
          <div className="text-2xs text-emerald-600 dark:text-emerald-400 mt-1 flex items-center gap-1">
            <CheckCircle2 className="h-2.5 w-2.5" />
            90 分 · 已达标
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-2xs text-ink-3 mb-1.5">最弱维度</div>
          <div className="text-2xl font-semibold text-ink-1 tracking-tight">系统设计</div>
          <div className="text-2xs text-amber-600 dark:text-amber-400 mt-1 flex items-center gap-1">
            <AlertCircle className="h-2.5 w-2.5" />
            75 分 · 急需提升
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* 雷达图 - 主视觉 */}
        <Card className="lg:col-span-2 p-6">
          <CardHeader
            title="能力雷达对比"
            description="蓝色 = 实际能力 · 灰色虚线 = 目标能力 · 点击维度查看详情"
            action={
              <Badge variant="brand" leftIcon={<Sparkles className="h-2.5 w-2.5" />}>
                {abilityDimensions.length} 维度
              </Badge>
            }
          />
          <RadarChart
            data={abilityDimensions}
            activeKey={activeDim}
            onSelect={setActiveDim}
          />
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-4">
            {abilityDimensions.map((d) => {
              const gap = d.ideal - d.actual
              return (
                <button
                  key={d.key}
                  onClick={() => setActiveDim(d.key === activeDim ? null : d.key)}
                  className={cn(
                    'text-left p-2 rounded-md border transition-all',
                    activeDim === d.key
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/10'
                      : 'border-surface-border dark:border-dark-surface-border hover:border-ink-muted/40',
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-ink-1">{d.name}</span>
                    <span
                      className={cn(
                        'text-2xs font-semibold tabular-nums',
                        gap <= 0
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : gap <= 10
                            ? 'text-brand-600 dark:text-brand-300'
                            : 'text-amber-600 dark:text-amber-400',
                      )}
                    >
                      {d.actual}
                      <span className="text-ink-3 font-normal">/{d.ideal}</span>
                    </span>
                  </div>
                  <div className="text-2xs text-ink-3 mt-0.5 flex items-center gap-1">
                    {gap <= 0 ? (
                      <>
                        <CheckCircle2 className="h-2.5 w-2.5 text-emerald-500" />
                        已达标
                      </>
                    ) : (
                      <>
                        <AlertCircle className="h-2.5 w-2.5 text-amber-500" />
                        差 {gap} 分
                      </>
                    )}
                  </div>
                </button>
              )
            })}
          </div>
        </Card>

        {/* 维度详情 */}
        <Card className="p-5">
          {(() => {
            const d = abilityDimensions.find((x) => x.key === activeDim) || abilityDimensions[1]
            const gap = d.ideal - d.actual
            return (
              <>
                <CardHeader
                  title={d.name}
                  description={d.description}
                  action={
                    <Badge variant={gap <= 0 ? 'success' : gap <= 10 ? 'brand' : 'warning'}>
                      {gap <= 0 ? '已达标' : `差 ${gap} 分`}
                    </Badge>
                  }
                />
                <div className="text-center py-3 mb-3 rounded-md bg-surface-muted dark:bg-dark-surface-muted">
                  <div className="text-3xl font-semibold text-ink-1 tabular-nums">{d.actual}</div>
                  <div className="text-2xs text-ink-3 mt-0.5">实际 / {d.ideal} 目标</div>
                </div>
                <div className="space-y-2">
                  <div className="text-xs font-medium text-ink-1 mb-2">子项得分</div>
                  {d.subItems.map((s) => (
                    <div key={s.name} className="space-y-1">
                      <div className="flex items-center justify-between text-2xs">
                        <span className="text-ink-2">{s.name}</span>
                        <span className="font-semibold tabular-nums text-ink-1">{s.score}</span>
                      </div>
                      <Progress value={s.score} size="sm" variant="brand" />
                    </div>
                  ))}
                </div>
                <div className="mt-3 pt-3 border-t border-surface-border dark:border-dark-surface-border">
                  <div className="text-xs font-medium text-ink-1 mb-2 flex items-center gap-1">
                    <Lightbulb className="h-3 w-3 text-amber-500" />
                    提升建议
                  </div>
                  <p className="text-xs text-ink-3 leading-relaxed">
                    {d.key === 'tech' && '继续深入 React 18 内部机制，完成官方 RFC 阅读。'}
                    {d.key === 'arch' && '完成 3 道 L4 级别系统设计题，重点关注容量预估和限流降级。'}
                    {d.key === 'eng' && '保持优势，准备 3 个最具说服力的工程化案例。'}
                    {d.key === 'comm' && '通过技术分享练习结构化表达，每月 1 次。'}
                    {d.key === 'algo' && '保持 LeetCode 每周 10 题节奏，重点是动态规划。'}
                    {d.key === 'biz' && '研究字节电商业务架构，建立业务方法论。'}
                  </p>
                </div>
              </>
            )
          })()}
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex items-center justify-between gap-3 mb-4">
        <Tabs
          value={tab}
          onChange={setTab}
          items={[
            { key: 'overview', label: '成长轨迹' },
            { key: 'suggestions', label: '提升建议', count: improvementSuggestions.length },
            { key: 'milestones', label: '里程碑' },
          ]}
        />
        {tab === 'overview' && (
          <div className="flex items-center gap-1">
            {[
              { key: '1m', label: '1月' },
              { key: '3m', label: '3月' },
              { key: '6m', label: '6月' },
              { key: 'all', label: '全部' },
            ].map((r) => (
              <button
                key={r.key}
                onClick={() => setTimeRange(r.key)}
                className={cn(
                  'px-2.5 h-7 rounded text-xs font-medium transition-colors',
                  timeRange === r.key
                    ? 'bg-surface-muted dark:bg-dark-surface-muted text-ink-1'
                    : 'text-ink-3 hover:text-ink-1 hover:bg-surface-muted/60 dark:hover:bg-dark-surface-muted/40',
                )}
              >
                {r.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {tab === 'overview' && (
        <Card className="mb-6">
          <CardHeader
            title="能力成长轨迹"
            description="6 个维度在过去 6 个月的变化曲线"
          />
          <GrowthChart data={growthTrajectory} />
        </Card>
      )}

      {tab === 'suggestions' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
          {improvementSuggestions.map((s) => (
            <Card key={s.id} hover padding="md">
              <div className="flex items-start gap-3 mb-3">
                <div
                  className={cn(
                    'h-9 w-9 rounded-md flex items-center justify-center flex-shrink-0',
                    s.priority === 'high'
                      ? 'bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400'
                      : s.priority === 'medium'
                        ? 'bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400'
                        : 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
                  )}
                >
                  {s.priority === 'high' ? (
                    <AlertCircle className="h-4 w-4" />
                  ) : s.priority === 'medium' ? (
                    <Lightbulb className="h-4 w-4" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-semibold text-ink-1">{s.title}</span>
                    <Badge
                      variant={
                        s.priority === 'high'
                          ? 'danger'
                          : s.priority === 'medium'
                            ? 'warning'
                            : 'success'
                      }
                      className="!h-4"
                    >
                      {s.priority === 'high' ? '紧急' : s.priority === 'medium' ? '建议' : '保持'}
                    </Badge>
                  </div>
                  <p className="text-xs text-ink-3 leading-relaxed mb-3">{s.description}</p>
                  <div className="space-y-1.5">
                    {s.actions.map((a, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 p-2 rounded-md bg-surface-muted/60 dark:bg-dark-surface-muted/30 hover:bg-surface-muted dark:hover:bg-dark-surface-muted transition-colors"
                      >
                        <div className="h-4 w-4 rounded-full bg-brand-500/15 text-brand-600 dark:text-brand-300 flex items-center justify-center text-2xs font-semibold flex-shrink-0 mt-0.5">
                          {i + 1}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs text-ink-1 leading-snug">{a.label}</div>
                          <div className="text-2xs text-ink-3 mt-0.5 flex items-center gap-1">
                            <Clock className="h-2.5 w-2.5" />
                            预计 {a.estimatedTime}
                          </div>
                        </div>
                        <button className="text-ink-3 hover:text-ink-1 transition-colors" aria-label="开始">
                          <ArrowRight className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {tab === 'milestones' && (
        <Card>
          <div className="relative pl-8 space-y-6 before:absolute before:left-3.5 before:top-2 before:bottom-2 before:w-px before:bg-surface-border dark:before:bg-dark-surface-border">
            {[
              { date: '2026-06-11', title: '完成 12 场模拟面试', desc: '累计时长超过 8 小时', icon: MessageSquare, tone: 'brand' },
              { date: '2026-06-08', title: '完成核心简历 V12 升级', desc: '整合 6 家公司分支', icon: FileText, tone: 'violet' },
              { date: '2026-06-02', title: '技术深度突破 80 分', desc: 'React 原理专项训练见效', icon: TrendingUp, tone: 'emerald' },
              { date: '2026-05-20', title: '工程实践达到目标', desc: 'CI/CD 体系完整建设', icon: Zap, tone: 'emerald' },
              { date: '2026-05-10', title: '加入 InterCraft', desc: '开始系统化求职准备', icon: Star, tone: 'amber' },
            ].map((m, i) => (
              <div key={i} className="relative">
                <div
                  className={cn(
                    'absolute -left-[27px] top-0 h-7 w-7 rounded-full flex items-center justify-center ring-4 ring-surface dark:ring-dark-surface',
                    m.tone === 'brand'
                      ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-600 dark:text-brand-300'
                      : m.tone === 'emerald'
                        ? 'bg-emerald-50 dark:bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                        : m.tone === 'violet'
                          ? 'bg-violet-50 dark:bg-violet-500/15 text-violet-600 dark:text-violet-400'
                          : 'bg-amber-50 dark:bg-amber-500/15 text-amber-600 dark:text-amber-400',
                  )}
                >
                  <m.icon className="h-3.5 w-3.5" />
                </div>
                <div className="text-2xs text-ink-3 mb-0.5">{m.date}</div>
                <div className="text-sm font-medium text-ink-1">{m.title}</div>
                <div className="text-xs text-ink-3 mt-0.5">{m.desc}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

// ============== 雷达图 SVG 组件 ==============
function RadarChart({
  data,
  activeKey,
  onSelect,
}: {
  data: typeof abilityDimensions
  activeKey: string | null
  onSelect: (key: string | null) => void
}) {
  const size = 360
  const cx = size / 2
  const cy = size / 2
  const radius = size / 2 - 50
  const levels = 5 // 网格层级
  const max = 100
  const angleStep = (Math.PI * 2) / data.length
  const startAngle = -Math.PI / 2 // 从顶部开始

  // 计算每个数据点的极坐标
  const point = (value: number, idx: number) => {
    const angle = startAngle + idx * angleStep
    const r = (value / max) * radius
    return [cx + Math.cos(angle) * r, cy + Math.sin(angle) * r]
  }

  // 实际能力多边形
  const actualPath = data
    .map((d, i) => point(d.actual, i))
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`)
    .join(' ') + ' Z'

  // 理想能力多边形
  const idealPath = data
    .map((d, i) => point(d.ideal, i))
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`)
    .join(' ') + ' Z'

  return (
    <div className="relative w-full flex items-center justify-center">
      <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-md">
        <defs>
          <linearGradient id="radar-actual" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(59, 130, 246)" stopOpacity="0.32" />
            <stop offset="100%" stopColor="rgb(59, 130, 246)" stopOpacity="0.08" />
          </linearGradient>
        </defs>

        {/* 网格层 */}
        {Array.from({ length: levels }).map((_, level) => {
          const r = ((level + 1) / levels) * radius
          const path = data
            .map((_, i) => {
              const angle = startAngle + i * angleStep
              const x = cx + Math.cos(angle) * r
              const y = cy + Math.sin(angle) * r
              return `${i === 0 ? 'M' : 'L'} ${x} ${y}`
            })
            .join(' ') + ' Z'
          return (
            <path
              key={level}
              d={path}
              fill="none"
              stroke="currentColor"
              strokeOpacity={0.08}
              strokeWidth="1"
            />
          )
        })}

        {/* 轴线 */}
        {data.map((_, i) => {
          const angle = startAngle + i * angleStep
          const x = cx + Math.cos(angle) * radius
          const y = cy + Math.sin(angle) * radius
          return (
            <line
              key={i}
              x1={cx}
              y1={cy}
              x2={x}
              y2={y}
              stroke="currentColor"
              strokeOpacity={0.06}
              strokeWidth="1"
            />
          )
        })}

        {/* 理想能力（虚线） */}
        <path
          d={idealPath}
          fill="none"
          stroke="rgb(148, 163, 184)"
          strokeOpacity="0.5"
          strokeWidth="1.5"
          strokeDasharray="4 4"
        />

        {/* 实际能力填充 */}
        <path
          d={actualPath}
          fill="url(#radar-actual)"
          stroke="rgb(59, 130, 246)"
          strokeWidth="2"
          strokeLinejoin="round"
        />

        {/* 数据点 + 标签 */}
        {data.map((d, i) => {
          const [x, y] = point(d.actual, i)
          const labelAngle = startAngle + i * angleStep
          const labelR = radius + 24
          const lx = cx + Math.cos(labelAngle) * labelR
          const ly = cy + Math.sin(labelAngle) * labelR
          const isActive = activeKey === d.key
          return (
            <g key={d.key}>
              <circle
                cx={x}
                cy={y}
                r={isActive ? 6 : 4}
                fill="white"
                stroke="rgb(59, 130, 246)"
                strokeWidth="2"
                className="cursor-pointer transition-all"
                onClick={() => onSelect(d.key === activeKey ? null : d.key)}
              />
              <text
                x={lx}
                y={ly}
                textAnchor="middle"
                dominantBaseline="middle"
                className={cn(
                  'fill-current text-2xs font-medium pointer-events-none cursor-pointer',
                  isActive ? 'text-brand-600 dark:text-brand-300' : 'text-ink-2 dark:text-dark-ink-secondary',
                )}
                onClick={() => onSelect(d.key === activeKey ? null : d.key)}
              >
                {d.name}
              </text>
              <text
                x={lx}
                y={ly + 11}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-current text-2xs tabular-nums pointer-events-none"
                style={{ fontSize: 9 }}
              >
                {d.actual}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

// ============== 成长曲线图 ==============
function GrowthChart({ data }: { data: typeof growthTrajectory }) {
  const dimensions: { key: keyof typeof data[0]; name: string; color: string }[] = [
    { key: 'tech', name: '技术深度', color: 'rgb(59, 130, 246)' },
    { key: 'arch', name: '系统设计', color: 'rgb(168, 85, 247)' },
    { key: 'eng', name: '工程实践', color: 'rgb(16, 185, 129)' },
    { key: 'comm', name: '沟通表达', color: 'rgb(245, 158, 11)' },
    { key: 'algo', name: '算法能力', color: 'rgb(236, 72, 153)' },
    { key: 'biz', name: '业务理解', color: 'rgb(20, 184, 166)' },
  ]

  const width = 800
  const height = 240
  const padding = { top: 20, right: 100, bottom: 30, left: 40 }
  const max = 100
  const min = 40
  const stepX = (width - padding.left - padding.right) / (data.length - 1)
  const stepY = (height - padding.top - padding.bottom) / (max - min)

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" preserveAspectRatio="none">
        <defs>
          {dimensions.map((d) => (
            <linearGradient
              key={d.key}
              id={`grad-${d.key}`}
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop offset="0%" stopColor={d.color} stopOpacity="0.15" />
              <stop offset="100%" stopColor={d.color} stopOpacity="0" />
            </linearGradient>
          ))}
        </defs>

        {/* Y 轴网格 */}
        {[0, 0.25, 0.5, 0.75, 1].map((p) => {
          const y = padding.top + (height - padding.top - padding.bottom) * p
          const value = max - (max - min) * p
          return (
            <g key={p}>
              <line
                x1={padding.left}
                x2={width - padding.right}
                y1={y}
                y2={y}
                stroke="currentColor"
                strokeOpacity="0.05"
                strokeDasharray="2 3"
              />
              <text
                x={padding.left - 6}
                y={y}
                textAnchor="end"
                dominantBaseline="middle"
                className="fill-current text-2xs text-ink-3"
                style={{ fontSize: 9 }}
              >
                {Math.round(value)}
              </text>
            </g>
          )
        })}

        {/* X 轴标签 */}
        {data.map((d, i) => {
          const x = padding.left + i * stepX
          return (
            <text
              key={i}
              x={x}
              y={height - padding.bottom + 16}
              textAnchor="middle"
              className="fill-current text-2xs text-ink-3"
              style={{ fontSize: 10 }}
            >
              {d.date}
            </text>
          )
        })}

        {/* 数据线 */}
        {dimensions.map((dim) => {
          const points = data.map((d, i) => {
            const x = padding.left + i * stepX
            const value = d[dim.key] as number
            const y = padding.top + (max - value) * stepY
            return [x, y]
          })
          const linePath = points
            .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`)
            .join(' ')
          const areaPath = `${linePath} L ${points[points.length - 1][0]} ${height - padding.bottom} L ${points[0][0]} ${height - padding.bottom} Z`
          return (
            <g key={dim.key}>
              <path d={areaPath} fill={`url(#grad-${dim.key})`} />
              <path
                d={linePath}
                fill="none"
                stroke={dim.color}
                strokeWidth="2"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {points.map(([x, y], i) => (
                <circle key={i} cx={x} cy={y} r="2.5" fill="white" stroke={dim.color} strokeWidth="1.5" />
              ))}
            </g>
          )
        })}
      </svg>

      {/* 图例 */}
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-2 justify-end pr-2">
        {dimensions.map((d) => (
          <div key={d.key} className="flex items-center gap-1.5 text-2xs text-ink-3">
            <span className="h-1.5 w-3 rounded-full" style={{ background: d.color }} />
            {d.name}
          </div>
        ))}
      </div>
    </div>
  )
}
