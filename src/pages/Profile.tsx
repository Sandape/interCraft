import { useState, useMemo } from 'react'
import {
  Download,
  Share2,
  TrendingUp,
  Target,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Lightbulb,
  Star,
  Loader2,
  MessageSquare,
  FileText,
  Zap,
} from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import AbilityUpdateStatus from '@/components/profile/AbilityUpdateStatus'
import { useAuthStore } from '@/stores/useAuthStore'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Progress } from '@/components/ui/Progress'
import { OfflineBanner } from '@/components/lock/OfflineBanner'
import { Tabs } from '@/components/ui/Tabs'
import { useAbilities, useDimensionsMeta, useAbilityHistory } from '@/hooks/queries/useAbilities'
import { usePatchAbility, useToggleAbility } from '@/hooks/mutations/usePatchAbility'
import type { AbilityDimension as ApiDim, DimensionMeta } from '@/repositories/AbilityRepository'
import { cn } from '@/lib/utils'

interface ChartDim {
  key: string
  name: string
  description: string
  ideal: number
  actual: number
  subItems: { name: string; score: number }[]
}

function transform(dim: ApiDim, metas: DimensionMeta[]): ChartDim {
  const meta = metas.find((m) => m.key === dim.dimension_key)
  const name = meta?.label_zh ?? dim.dimension_key
  const description = meta?.label_en ?? ''
  const subItems = meta?.sub_keys
    ? meta.sub_keys.map((sk) => ({
        name: sk.label_zh,
        score: Number(dim.sub_scores?.[sk.key]?.actual ?? 0),
      }))
    : Object.entries(dim.sub_scores ?? {}).map(([k, v]) => ({ name: k, score: Number(v.actual) }))
  return {
    key: dim.dimension_key,
    name,
    description,
    ideal: Number(dim.ideal_score ?? 0),
    actual: Number(dim.actual_score ?? 0),
    subItems,
  }
}

export default function Profile() {
  const [activeDim, setActiveDim] = useState<string | null>(null)
  const [tab, setTab] = useState('overview')

  const { data: abilitiesData, isLoading } = useAbilities(true)
  const { data: metaData } = useDimensionsMeta()
  const { data: historyData } = useAbilityHistory(undefined, 'month')
  const patchAbility = usePatchAbility()
  const toggleAbility = useToggleAbility()
  const currentUser = useAuthStore((s) => s.user)

  const metas = metaData?.dimensions ?? []
  const allDimensions = useMemo(() => {
    if (!abilitiesData?.data) return []
    return abilitiesData.data
      .filter((d) => d.is_active)
      .map((d) => transform(d, metas))
  }, [abilitiesData, metas])

  const overallIdeal = Math.round(
    allDimensions.length ? allDimensions.reduce((s, d) => s + d.ideal, 0) / allDimensions.length : 0,
  )
  const overallActual = Math.round(
    allDimensions.length ? allDimensions.reduce((s, d) => s + d.actual, 0) / allDimensions.length : 0,
  )
  const gap = overallIdeal - overallActual

  const historyPoints = historyData?.data ?? []
  const growth = historyPoints.length >= 2
    ? Math.round(historyPoints[historyPoints.length - 1].actual_score - historyPoints[0].actual_score)
    : 0

  const bestDim = allDimensions.length
    ? allDimensions.reduce((a, b) => (a.actual >= b.actual ? a : b))
    : null
  const worstDim = allDimensions.length
    ? allDimensions.reduce((a, b) => (a.actual <= b.actual ? a : b))
    : null

  if (isLoading) {
    return (
      <div className="px-8 py-6 max-w-7xl mx-auto flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 text-ink-3 animate-spin" />
      </div>
    )
  }

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto">
      {/* 页头 */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">个人能力画像</h1>
          <p className="text-sm text-ink-3 mt-1">
            对比理想与真实能力，量化差距，AI 生成针对性提升路径
          </p>
          <div className="mt-2">
            <AbilityUpdateStatus userId={currentUser?.id ?? null} />
          </div>
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
          <div className="text-2xl font-semibold text-ink-1 tracking-tight">
            {bestDim?.name ?? '—'}
          </div>
          <div className="text-2xs text-emerald-600 dark:text-emerald-400 mt-1 flex items-center gap-1">
            <CheckCircle2 className="h-2.5 w-2.5" />
            {bestDim ? `${bestDim.actual} 分 · 已达标` : '暂无数据'}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-2xs text-ink-3 mb-1.5">最弱维度</div>
          <div className="text-2xl font-semibold text-ink-1 tracking-tight">
            {worstDim?.name ?? '—'}
          </div>
          <div className="text-2xs text-amber-600 dark:text-amber-400 mt-1 flex items-center gap-1">
            <AlertCircle className="h-2.5 w-2.5" />
            {worstDim ? `${worstDim.actual} 分 · 差距 ${worstDim.ideal - worstDim.actual} 分` : '暂无数据'}
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
                {allDimensions.length} 维度
              </Badge>
            }
          />
          <div data-testid="radar-chart">
            <RadarChart
              data={allDimensions}
              activeKey={activeDim}
              onSelect={setActiveDim}
            />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-4" data-testid="dimension-score-list">
            {allDimensions.map((d) => {
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
                  data-testid={`dimension-score-${d.key}`}
                  data-actual-score={d.actual}
                  data-ideal-score={d.ideal}
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
            const d = allDimensions.find((x) => x.key === activeDim) || allDimensions[0]
            if (!d) return <p className="text-sm text-ink-3 py-8 text-center">暂无能力数据</p>
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
                  <ul className="suggestion-list text-xs text-ink-3 leading-relaxed space-y-1">
                    <li>
                      {gap > 0
                        ? `当前差距 ${gap} 分，建议针对性练习提升该维度。`
                        : '已达到目标，继续保持现有水平。'}
                    </li>
                  </ul>
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
            { key: 'suggestions', label: '提升建议' },
            { key: 'milestones', label: '里程碑' },
          ]}
        />
      </div>

      {tab === 'overview' && (
        <Card className="mb-6">
          <CardHeader
            title="能力成长轨迹"
            description="6 个维度在过去 6 个月的变化曲线"
          />
          <HistoryChart data={historyPoints} />
        </Card>
      )}

      {tab === 'suggestions' && (
        <Card className="p-5 text-center text-sm text-ink-3">
          <Lightbulb className="h-6 w-6 text-ink-muted mx-auto mb-2" />
          提升建议将在完成更多模拟面试后由 AI 自动生成
        </Card>
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
      <OfflineBanner />
    </div>
  )
}

// ============== 雷达图 SVG 组件 ==============
function RadarChart({
  data,
  activeKey,
  onSelect,
}: {
  data: ChartDim[]
  activeKey: string | null
  onSelect: (key: string | null) => void
}) {
  const size = 360
  const cx = size / 2
  const cy = size / 2
  const radius = size / 2 - 50
  const levels = 5 // 网格层级
  const max = 100

  if (data.length === 0) {
    return (
      <div className="relative w-full flex items-center justify-center">
        <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-md">
          <text
            x={cx}
            y={cy - 8}
            textAnchor="middle"
            dominantBaseline="middle"
            className="fill-current text-sm text-ink-3"
          >
            暂无能力数据
          </text>
          <text
            x={cx}
            y={cy + 14}
            textAnchor="middle"
            dominantBaseline="middle"
            className="fill-current text-2xs text-ink-4"
          >
            完成模拟面试后生成能力画像
          </text>
        </svg>
      </div>
    )
  }

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
function HistoryChart({ data }: { data: { snapshot_date: string; actual_score: number }[] }) {
  // Group by date and compute average
  const grouped = useMemo(() => {
    const map = new Map<string, { total: number; count: number }>()
    for (const p of data) {
      const d = p.snapshot_date.slice(0, 7) // YYYY-MM
      const cur = map.get(d) ?? { total: 0, count: 0 }
      cur.total += p.actual_score
      cur.count += 1
      map.set(d, cur)
    }
    return Array.from(map.entries())
      .map(([date, v]) => ({ date, value: Math.round(v.total / v.count) }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  if (grouped.length < 2) {
    return <div className="text-xs text-ink-3 text-center py-12">完成更多模拟面试后生成成长轨迹</div>
  }

  const width = 800
  const height = 240
  const padding = { top: 20, right: 40, bottom: 30, left: 40 }
  const maxVal = 100
  const minVal = Math.max(0, Math.min(...grouped.map((g) => g.value)) - 10)
  const stepX = (width - padding.left - padding.right) / (grouped.length - 1)
  const stepY = (height - padding.top - padding.bottom) / (maxVal - minVal)

  const points = grouped.map((g, i) => {
    const x = padding.left + i * stepX
    const y = padding.top + (maxVal - g.value) * stepY
    return [x, y, g.value] as const
  })
  const linePath = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'} ${x} ${y}`).join(' ')
  const areaPath = `${linePath} L ${points[points.length - 1][0]} ${height - padding.bottom} L ${points[0][0]} ${height - padding.bottom} Z`

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
        <defs>
          <linearGradient id="grad-history" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(59, 130, 246)" stopOpacity="0.15" />
            <stop offset="100%" stopColor="rgb(59, 130, 246)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 0.25, 0.5, 0.75, 1].map((p) => {
          const y = padding.top + (height - padding.top - padding.bottom) * p
          return (
            <g key={p}>
              <line x1={padding.left} x2={width - padding.right} y1={y} y2={y} stroke="currentColor" strokeOpacity="0.05" strokeDasharray="2 3" />
              <text x={padding.left - 6} y={y} textAnchor="end" dominantBaseline="middle" className="fill-current text-2xs text-ink-3" style={{ fontSize: 9 }}>
                {Math.round(maxVal - (maxVal - minVal) * p)}
              </text>
            </g>
          )
        })}
        {grouped.map((g, i) => {
          const x = padding.left + i * stepX
          return (
            <text key={i} x={x} y={height - padding.bottom + 16} textAnchor="middle" className="fill-current text-2xs text-ink-3" style={{ fontSize: 10 }}>
              {g.date}
            </text>
          )
        })}
        <path d={areaPath} fill="url(#grad-history)" />
        <path d={linePath} fill="none" stroke="rgb(59, 130, 246)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {points.map(([x, y, v], i) => (
          <g key={i}>
            <circle cx={x} cy={y} r="3" fill="white" stroke="rgb(59, 130, 246)" strokeWidth="1.5" />
            <text x={x} y={y - 8} textAnchor="middle" className="fill-current text-2xs text-ink-1" style={{ fontSize: 9 }}>{v}</text>
          </g>
        ))}
      </svg>
    </div>
  )
}
