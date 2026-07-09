/**
 * REQ-057 — 求职训练指挥台（工作台首页）
 * Single data source: GET /me/dashboard-summary
 */
import { Link } from 'react-router-dom'
import {
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
import { useAuthStore } from '@/stores/useAuthStore'
import { timeAgo } from '@/lib/utils'
import {
  useDashboardSummary,
  type DashboardSummary,
} from '@/hooks/queries/useDashboardSummary'

export default function Dashboard() {
  const user = useAuthStore((s) => s.user)
  const { data: summary, isLoading, isError, refetch, isFetching } = useDashboardSummary()

  const l0 = summary?.l0
  const l1 = summary?.l1
  const l2 = summary?.l2
  const resumeTotal = l1?.resume_counts.total ?? 0
  const interviewsCompleted = l2?.interview_trend?.completed_count ?? 0
  const overallAbility = l2?.ability_snapshot?.overall_score ?? 0
  const averageScore = l2?.interview_trend?.avg_score ?? 0

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto pb-24 md:pb-6" data-testid="dashboard-command-center">
      {/* L0 — 今日指挥台 */}
      <div className="mb-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">
              {getGreeting()}，{user?.display_name || '用户'}
            </h1>
            <p className="text-sm text-ink-3 mt-1" data-testid="dashboard-greeting-context">
              {isLoading && !summary
                ? '正在加载今日安排…'
                : l0?.greeting_context || '开始你的求职训练'}
            </p>
            {l0?.next_interview && (
              <p className="text-sm text-ink-2 mt-2" data-testid="dashboard-next-interview">
                下一场：
                <Link to={l0.next_interview.href} className="text-brand-600 hover:underline ml-1">
                  {l0.next_interview.company} · {l0.next_interview.position}
                </Link>
                <span className="text-ink-3 ml-2">{l0.next_interview.relative_label}</span>
              </p>
            )}
          </div>
          <div className="hidden md:flex items-center gap-2 flex-shrink-0">
            <PrimaryCta cta={l0?.primary_cta} />
            <Link to="/resume">
              <Button variant="secondary" leftIcon={<FileText className="h-3.5 w-3.5" />}>
                简历中心
              </Button>
            </Link>
          </div>
        </div>

        {l0?.onboarding?.show && (
          <div
            className="mt-4 rounded-lg border border-surface-border dark:border-dark-surface-border p-4"
            data-testid="dashboard-onboarding"
          >
            <div className="text-xs font-medium text-ink-2 mb-3">开始三步</div>
            <ol className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {l0.onboarding.steps.map((step, idx) => (
                <li key={step.id}>
                  <Link
                    to={step.href}
                    className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors ${
                      step.done
                        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'
                        : 'bg-surface-muted/60 text-ink-1 hover:bg-surface-muted'
                    }`}
                  >
                    <span className="tabular-nums text-ink-3">{idx + 1}</span>
                    <span className="flex-1">
                      {step.id === 'resume' && '完善简历'}
                      {step.id === 'job' && '登记岗位'}
                      {step.id === 'interview' && '首场模拟面试'}
                    </span>
                    {step.done ? <Badge variant="success">完成</Badge> : <ChevronRight className="h-3.5 w-3.5" />}
                  </Link>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>

      {/* 可点击指标（无假涨跌） */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <Link to="/resume" className="block">
          <StatCard
            icon={<FileText className="h-4 w-4" />}
            label="简历"
            value={resumeTotal}
            suffix="份"
            changeLabel={resumeTotal > 0 ? `${l1?.resume_counts.root ?? 0} 根 · ${l1?.resume_counts.derived ?? 0} 派生` : '去简历中心'}
          />
        </Link>
        <Link to="/interview" className="block">
          <StatCard
            icon={<MessageSquareText className="h-4 w-4" />}
            label="已完成面试"
            value={interviewsCompleted}
            suffix="场"
            changeLabel={interviewsCompleted > 0 ? `均分 ${averageScore}` : '完成面试后生成'}
          />
        </Link>
        <Link to="/ability-profile" className="block">
          <StatCard
            icon={<Radar className="h-4 w-4" />}
            label="综合能力"
            value={overallAbility}
            suffix="/ 10"
            changeLabel={overallAbility > 0 ? '查看完整画像' : '完成面试后生成'}
            isFloat
          />
        </Link>
        <Link to="/jobs" className="block">
          <StatCard
            icon={<Briefcase className="h-4 w-4" />}
            label="岗位追踪"
            value={(l1?.job_funnel ?? []).reduce((a, s) => a + s.count, 0)}
            suffix="个"
            changeLabel="查看漏斗"
          />
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* 单一「下一步」建议 */}
        <Card className="lg:col-span-2 p-5" data-testid="dashboard-next-action">
          <div className="flex items-start gap-3">
            <div className="h-8 w-8 rounded-md bg-brand-50 dark:bg-brand-500/15 flex items-center justify-center flex-shrink-0">
              <Lightbulb className="h-4 w-4 text-brand-600 dark:text-brand-300" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-ink-1 mb-1">下一步</h3>
              {l1?.next_action ? (
                <div className="text-sm text-ink-2 leading-relaxed">
                  <div className="font-medium text-ink-1">{l1.next_action.title_zh}</div>
                  <p className="mt-0.5">{l1.next_action.body_zh}</p>
                  <Link
                    to={l1.next_action.cta.href}
                    className="inline-flex items-center gap-1 mt-1.5 text-xs text-brand-600 dark:text-brand-300 hover:underline"
                    data-testid="dashboard-next-action-cta"
                  >
                    {l1.next_action.cta.label} <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
              ) : (
                <p className="text-sm text-ink-3 py-2">{isLoading ? '加载建议…' : '暂无建议'}</p>
              )}
            </div>
          </div>
        </Card>

        {/* 今日面试 */}
        <Card className="p-5" data-testid="dashboard-today-interviews">
          <CardHeader
            title="今日面试"
            description={`${l0?.today_interviews.length ?? 0} 场`}
            action={
              <Link
                to="/jobs"
                className="text-2xs text-ink-3 hover:text-ink-1 transition-colors inline-flex items-center gap-0.5"
                data-testid="dashboard-today-all"
              >
                全部 <ChevronRight className="h-3 w-3" />
              </Link>
            }
          />
          {(l0?.today_interviews.length ?? 0) > 0 ? (
            <ul className="space-y-2">
              {l0!.today_interviews.map((t) => (
                <li key={t.job_id}>
                  <Link
                    to={t.href}
                    className="flex items-start gap-2.5 -mx-1.5 px-1.5 py-1.5 rounded hover:bg-surface-muted/60 dark:hover:bg-dark-surface-muted/40 transition-colors"
                    data-testid="dashboard-today-item"
                  >
                    <Clock className="mt-0.5 h-3.5 w-3.5 text-ink-3 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-ink-1 leading-snug truncate">
                        {t.company} · {t.position}
                      </div>
                      <div className="text-2xs text-ink-3 mt-0.5">{t.relative_label}</div>
                    </div>
                    <ArrowUpRight className="h-3.5 w-3.5 text-ink-muted flex-shrink-0" />
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-ink-3 py-3 text-center">
              <p>今天没有安排面试</p>
              <Link to="/jobs" className="text-xs text-brand-600 hover:underline mt-1 inline-block">
                去求职追踪登记
              </Link>
            </div>
          )}
          {l1?.prep_pack && (l0?.today_interviews.length ?? 0) > 0 && (
            <div className="mt-3 pt-3 border-t border-surface-border dark:border-dark-surface-border flex flex-wrap gap-2" data-testid="dashboard-prep-pack">
              {l1.prep_pack.actions.map((a) => (
                <Link key={a.href + a.label} to={a.href}>
                  <Button variant="secondary" className="!h-7 !text-xs">
                    {a.label}
                  </Button>
                </Link>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* 继续未完成 + 漏斗 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {(l0?.resumable_sessions.length ?? 0) > 0 && (
          <Card className="p-5" data-testid="dashboard-continue">
            <CardHeader title="继续未完成" description="进行中的模拟面试" />
            <ul className="space-y-2">
              {l0!.resumable_sessions.map((s) => (
                <li key={s.session_id}>
                  <Link
                    to={s.href}
                    className="flex items-center gap-2 text-sm text-ink-1 hover:text-brand-600"
                  >
                    <Zap className="h-3.5 w-3.5" />
                    <span className="truncate">
                      {[s.company, s.position].filter(Boolean).join(' · ') || '模拟面试'}
                    </span>
                    <Badge variant="warning">{s.status === 'in_progress' ? '进行中' : '待开始'}</Badge>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        )}

        <Card className={`p-5 ${(l0?.resumable_sessions.length ?? 0) > 0 ? 'lg:col-span-2' : 'lg:col-span-3'}`} data-testid="dashboard-funnel">
          <CardHeader title="求职漏斗" description="岗位追踪状态汇总" />
          {(l1?.job_funnel.length ?? 0) > 0 ? (
            <div className="grid grid-cols-3 gap-2">
              {l1!.job_funnel.map((seg) => (
                <Link
                  key={seg.key}
                  to={seg.href}
                  className="rounded-md border border-surface-border dark:border-dark-surface-border px-3 py-3 text-center hover:bg-surface-muted/50 transition-colors"
                  data-testid={`dashboard-funnel-${seg.key}`}
                >
                  <div className="text-xl font-semibold tabular-nums text-ink-1">{seg.count}</div>
                  <div className="text-2xs text-ink-3 mt-0.5">{seg.label_zh}</div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink-3 text-center py-3">
              暂无岗位 ·{' '}
              <Link to="/jobs" className="text-brand-600 hover:underline">
                去登记
              </Link>
            </p>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* 简历中心摘要 */}
        <Card className="lg:col-span-2" data-testid="dashboard-resumes">
          <CardHeader
            title="我的简历"
            description={
              resumeTotal > 0
                ? `${l1?.resume_counts.root ?? 0} 根 · ${l1?.resume_counts.derived ?? 0} 派生 · 共 ${resumeTotal}`
                : '与简历中心同步'
            }
            action={
              <Link to="/resume" className="text-xs text-brand-600 dark:text-brand-300 hover:underline">
                管理 →
              </Link>
            }
          />
          <div className="space-y-1.5">
            {(l1?.resume_summaries.length ?? 0) > 0 ? (
              l1!.resume_summaries.map((r) => (
                <Link
                  key={r.id}
                  to={r.href}
                  className="flex items-center gap-3 px-2 py-2 -mx-2 rounded hover:bg-surface-muted/60 dark:hover:bg-dark-surface-muted/40 transition-colors group"
                  data-testid="dashboard-resume-item"
                >
                  <div
                    className={`h-8 w-8 rounded-md flex items-center justify-center flex-shrink-0 ${
                      r.resume_kind === 'root'
                        ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-600'
                        : 'bg-surface-muted text-ink-2'
                    }`}
                  >
                    {r.resume_kind === 'root' ? (
                      <Sparkles className="h-3.5 w-3.5" />
                    ) : (
                      <Briefcase className="h-3.5 w-3.5" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-ink-1 truncate">{r.name}</div>
                    <div className="text-2xs text-ink-3 mt-0.5">
                      {kindLabel(r.resume_kind)}
                      {r.updated_at ? ` · ${timeAgo(r.updated_at)}` : ''}
                    </div>
                  </div>
                  <ArrowUpRight className="h-3.5 w-3.5 text-ink-muted opacity-0 group-hover:opacity-100" />
                </Link>
              ))
            ) : (
              <p className="text-sm text-ink-3 py-3 text-center">
                暂无简历，去
                <Link to="/resume" className="text-brand-600 hover:underline mx-1">
                  简历中心
                </Link>
                创建
              </p>
            )}
          </div>
        </Card>

        {/* 最近活动 */}
        <Card data-testid="dashboard-activities">
          <CardHeader
            title="最近活动"
            description="平台内的关键事件"
            action={<Activity className="h-3.5 w-3.5 text-ink-3" />}
          />
          <div className="space-y-3">
            {(l2?.recent_activities.length ?? 0) > 0 ? (
              l2!.recent_activities.map((a) => {
                const body = (
                  <>
                    <div className="text-xs text-ink-1 leading-snug" data-testid="dashboard-activity-title">
                      {a.title_zh}
                    </div>
                    {a.detail_zh && <div className="text-2xs text-ink-3 mt-0.5">{a.detail_zh}</div>}
                    {a.occurred_at && (
                      <div className="text-2xs text-ink-muted mt-0.5">{timeAgo(a.occurred_at)}</div>
                    )}
                  </>
                )
                return a.href ? (
                  <Link key={a.id} to={a.href} className="block hover:opacity-90">
                    {body}
                  </Link>
                ) : (
                  <div key={a.id}>{body}</div>
                )
              })
            ) : (
              <p className="text-sm text-ink-3 py-3 text-center">
                {isError ? (
                  <button type="button" className="text-brand-600 hover:underline" onClick={() => refetch()}>
                    加载失败，点击重试
                  </button>
                ) : (
                  '暂无活动记录'
                )}
              </p>
            )}
          </div>
        </Card>
      </div>

      {/* L2 能力概览 */}
      <Card className="mb-6" data-testid="dashboard-ability">
        <CardHeader
          title="能力概览"
          description={
            l2?.ability_snapshot
              ? `综合 ${l2.ability_snapshot.overall_score} 分`
              : '完成模拟面试后生成能力数据'
          }
          action={
            <Link to="/ability-profile" className="text-xs text-brand-600 dark:text-brand-300 hover:underline">
              查看详情 →
            </Link>
          }
        />
        {l2?.ability_snapshot?.weakest_dimensions?.length ? (
          <div className="space-y-3">
            {l2.ability_snapshot.weakest_dimensions.map((d) => (
              <div key={d.key} className="grid grid-cols-12 gap-3 items-center">
                <div className="col-span-3 sm:col-span-2 text-sm font-medium text-ink-1">{d.label_zh}</div>
                <div className="col-span-7 sm:col-span-8">
                  <Progress value={Math.min(d.actual_score * 10, 100)} size="md" variant="brand" />
                </div>
                <div className="col-span-2 text-sm text-ink-1 font-semibold tabular-nums text-right">
                  {d.actual_score}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-ink-3 py-3 text-center">
            {isFetching && !summary ? '加载中…' : '完成模拟面试后生成能力数据'}
          </p>
        )}
      </Card>

      {/* 移动端主 CTA */}
      <div className="md:hidden fixed bottom-0 inset-x-0 z-40 border-t border-surface-border dark:border-dark-surface-border bg-surface/95 backdrop-blur px-4 py-3">
        <PrimaryCta cta={l0?.primary_cta} fullWidth />
      </div>
    </div>
  )
}

function PrimaryCta({
  cta,
  fullWidth,
}: {
  cta: DashboardSummary['l0']['primary_cta'] | undefined
  fullWidth?: boolean
}) {
  const href = cta?.href || '/interview/mode'
  const label = cta?.label || '开始模拟面试'
  return (
    <Link to={href} className={fullWidth ? 'block' : undefined} data-testid="dashboard-primary-cta">
      <Button
        variant="primary"
        leftIcon={<Zap className="h-3.5 w-3.5" />}
        className={fullWidth ? 'w-full' : undefined}
      >
        {label}
      </Button>
    </Link>
  )
}

function kindLabel(kind: string): string {
  if (kind === 'root') return '根简历'
  if (kind === 'derived') return '派生简历'
  return '标准简历'
}

function getGreeting(): string {
  const h = new Date().getHours()
  if (h < 12) return '早上好'
  if (h < 18) return '下午好'
  return '晚上好'
}

function StatCard({
  icon,
  label,
  value,
  suffix,
  changeLabel,
  isFloat,
}: {
  icon: React.ReactNode
  label: string
  value: number
  suffix?: string
  changeLabel: string
  isFloat?: boolean
}) {
  const display = isFloat ? value.toFixed(1) : value
  return (
    <Card className="p-4 hover:shadow-notion transition-shadow h-full">
      <div className="flex items-start justify-between mb-2.5">
        <div className="h-7 w-7 rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-2 dark:text-dark-ink-secondary flex items-center justify-center">
          {icon}
        </div>
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
