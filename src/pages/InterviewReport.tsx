import { Link, useParams } from 'react-router-dom'
import { useState } from 'react'
import {
  ArrowLeft,
  Download,
  Share2,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  Lightbulb,
  ThumbsUp,
  Clock,
  Calendar,
  MessageSquare,
  Mic,
  ChevronRight,
  ChevronsUpDown,
  Loader2,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Progress } from '@/components/ui/Progress'
import { Avatar } from '@/components/ui/Avatar'
import { useInterviewSession } from '@/hooks/queries/useInterviewSessions'
import { useQuery } from '@tanstack/react-query'
import { interviewSessionRepo, type InterviewReport as ReportData } from '@/repositories/interviewSessionRepo'
import { cn, formatDuration, timeAgo } from '@/lib/utils'
import { dimensionLabel } from '@/lib/dimensions'

export default function InterviewReport() {
  const { id = '' } = useParams<{ id: string }>()
  const { data: session, isLoading: sessionLoading } = useInterviewSession(id)
  const { data: reportResp, isLoading: reportLoading } = useQuery({
    queryKey: ['interviewReport', id],
    queryFn: () => interviewSessionRepo.getReport(id),
    enabled: !!id,
  })

  const report: ReportData | null = reportResp?.data || null
  const isLoading = sessionLoading || reportLoading

  const [openSet, setOpenSet] = useState<Set<number>>(() => new Set())
  const toggle = (n: number) =>
    setOpenSet((prev) => {
      const next = new Set(prev)
      if (next.has(n)) next.delete(n)
      else next.add(n)
      return next
    })

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-ink-3" />
      </div>
    )
  }

  if (!session) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="text-lg font-semibold text-ink-1 mb-2">面试记录不存在</div>
          <Link to="/interview" className="text-sm text-brand-600 hover:underline">
            返回面试列表
          </Link>
        </div>
      </div>
    )
  }

  const displayScore = report?.overall_score || session.overall_score || session.score || 0
  const displayMode = session.mode === 'voice' ? '语音面试' : '文字面试'
  const scoreLabel = displayScore >= 8 ? '优秀' : displayScore >= 6 ? '良好' : '待提升'

  const dimensionScores = report?.dimension_scores || {}
  const dimensionEntries = Object.entries(dimensionScores)
  const bestDimension = dimensionEntries.length > 0
    ? dimensionEntries.reduce((a, b) => a[1] > b[1] ? a : b)
    : null
  const worstDimension = dimensionEntries.length > 0
    ? dimensionEntries.reduce((a, b) => a[1] < b[1] ? a : b)
    : null

  const perQuestion = report?.per_question_score || []
  const allOpen = perQuestion.length > 0 && openSet.size === perQuestion.length
  const expandAll = () => setOpenSet(new Set(perQuestion.map((q) => q.question_no)))
  const collapseAll = () => setOpenSet(new Set())

  const clamp10 = (s: number) => Math.max(0, Math.min(10, s))
  const ringStroke = (s: number) =>
    s >= 8 ? 'rgb(16, 185, 129)' : s >= 6 ? 'rgb(59, 130, 246)' : 'rgb(245, 158, 11)'
  const ringGlow = (s: number) =>
    s >= 8 ? 'rgba(16, 185, 129, 0.35)' : s >= 6 ? 'rgba(59, 130, 246, 0.35)' : 'rgba(245, 158, 11, 0.35)'
  const tierBadge = (s: number) =>
    s >= 8
      ? 'bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
      : s >= 6
        ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300'
        : 'bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400'
  const tierText = (s: number) =>
    s >= 8
      ? 'text-emerald-600 dark:text-emerald-400'
      : s >= 6
        ? 'text-brand-600 dark:text-brand-300'
        : 'text-amber-600 dark:text-amber-400'

  return (
    <div className="px-8 py-6 max-w-6xl mx-auto">
      {/* 页头 */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <Link
            to="/interview"
            className="inline-flex items-center gap-1 text-xs text-ink-3 hover:text-ink-1 transition-colors mb-2"
          >
            <ArrowLeft className="h-3 w-3" />
            返回面试历史
          </Link>
          <div className="flex items-center gap-2.5 mb-1">
            <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">
              {session.company || '未知公司'} · {session.position || '未知岗位'}
            </h1>
            <Badge variant={displayScore >= 8 ? 'success' : displayScore >= 6 ? 'brand' : 'warning'}>
              {scoreLabel}
            </Badge>
          </div>
          <div className="flex items-center gap-3 text-sm text-ink-3">
            <span className="flex items-center gap-1">
              <Calendar className="h-3.5 w-3.5" />
              {timeAgo(session.created_at)}
            </span>
            {session.duration_seconds ? (
              <>
                <span>·</span>
                <span className="flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" />
                  {formatDuration(session.duration_seconds)}
                </span>
              </>
            ) : null}
            <span>·</span>
            <span className="flex items-center gap-1">
              {session.mode === 'voice' ? <Mic className="h-3.5 w-3.5" /> : <MessageSquare className="h-3.5 w-3.5" />}
              {displayMode}
            </span>
            {session.question_count && (
              <>
                <span>·</span>
                <span>{session.question_count} 道题</span>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" leftIcon={<Share2 className="h-3.5 w-3.5" />}>
            分享报告
          </Button>
          <Button variant="primary" leftIcon={<Download className="h-3.5 w-3.5" />}>
            导出 PDF
          </Button>
        </div>
      </div>

      {/* 总览卡 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-6">
        <Card className="md:col-span-2 p-6 bg-gradient-to-br from-brand-50/40 to-surface dark:from-brand-500/5 dark:to-dark-surface">
          <div className="flex items-center gap-5">
            <div className="relative">
              <svg className="h-24 w-24 -rotate-90" viewBox="0 0 100 100" style={{ filter: `drop-shadow(0 0 6px ${ringGlow(displayScore)})` }}>
                <circle
                  cx="50" cy="50" r="42" fill="none"
                  stroke="currentColor" strokeOpacity="0.08" strokeWidth="8"
                />
                <circle
                  cx="50" cy="50" r="42" fill="none"
                  stroke={ringStroke(displayScore)} strokeWidth="8"
                  strokeDasharray={`${(clamp10(displayScore) / 10) * 264} 264`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center flex-col">
                <div className="text-2xl font-semibold text-ink-1 tabular-nums">
                  {displayScore} <span className="text-sm text-ink-3">/ 10</span>
                </div>
                <div className="text-2xs text-ink-3">综合评分 · 满分 10</div>
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 mb-1">
                <Sparkles className="h-3.5 w-3.5 text-brand-500" />
                <span className="text-xs font-medium text-brand-600 dark:text-brand-300">AI 总结</span>
              </div>
              <div className="text-sm text-ink-2 leading-relaxed [&_p]:mb-2 [&_strong]:font-semibold">
                {report?.summary_md ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.summary_md}</ReactMarkdown>
                ) : (
                  '暂无 AI 总结'
                )}
              </div>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-2xs text-ink-3 mb-1.5">最强维度</div>
          <div className="text-xl font-semibold text-ink-1">
            {bestDimension ? dimensionLabel(bestDimension[0]) : '—'}
          </div>
          <div className="text-2xs text-ink-3 mt-0.5">
            {bestDimension ? `${bestDimension[1]} 分 · 保持优势` : '暂无数据'}
          </div>
          {bestDimension && (() => {
            const strength = report?.strengths?.find((s) => s.dimension === bestDimension[0])
            if (strength?.detail) {
              return (
                <div className="mt-3 p-2 rounded-md bg-emerald-50/60 dark:bg-emerald-500/10 text-2xs text-emerald-700 dark:text-emerald-400 leading-relaxed">
                  {strength.detail}
                </div>
              )
            }
            return (
              <div className="mt-3 p-2 rounded-md bg-emerald-50 dark:bg-emerald-500/10 text-2xs text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
                <TrendingUp className="h-3 w-3" />
                表现最佳
              </div>
            )
          })()}
        </Card>

        <Card className="p-4">
          <div className="text-2xs text-ink-3 mb-1.5">最弱维度</div>
          <div className="text-xl font-semibold text-ink-1">
            {worstDimension ? dimensionLabel(worstDimension[0]) : '—'}
          </div>
          <div className="text-2xs text-ink-3 mt-0.5">
            {worstDimension ? `${worstDimension[1]} 分 · 急需提升` : '暂无数据'}
          </div>
          {worstDimension && (() => {
            const improvement = report?.improvements?.find((s) => s.dimension === worstDimension[0])
            if (improvement?.detail) {
              return (
                <div className="mt-3 p-2 rounded-md bg-amber-50/60 dark:bg-amber-500/10 text-2xs text-amber-700 dark:text-amber-400 leading-relaxed">
                  {improvement.detail}
                </div>
              )
            }
            return (
              <div className="mt-3 p-2 rounded-md bg-amber-50 dark:bg-amber-500/10 text-2xs text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
                <AlertCircle className="h-3 w-3" />
                影响整体评分
              </div>
            )
          })()}
        </Card>
      </div>

      {/* 五维表现 */}
      {dimensionEntries.length > 0 && (
        <Card className="mb-6 p-5">
          <CardHeader
            title="五维能力表现"
            description="各维度评分概览"
          />
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {dimensionEntries.map(([name, score]) => (
              <div key={name} className="text-center">
                <div className="relative inline-block mb-2">
                  <svg className="h-20 w-20 -rotate-90" viewBox="0 0 100 100" style={{ filter: `drop-shadow(0 0 5px ${ringGlow(score)})` }}>
                    <circle cx="50" cy="50" r="40" fill="none"
                      stroke="currentColor" strokeOpacity="0.08" strokeWidth="6"
                    />
                    <circle cx="50" cy="50" r="40" fill="none"
                      stroke={ringStroke(score)} strokeWidth="6"
                      strokeDasharray={`${(clamp10(score) / 10) * 251} 251`}
                      strokeLinecap="round"
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-lg font-semibold text-ink-1 tabular-nums">{score}</span>
                  </div>
                </div>
                <div className="text-xs font-medium text-ink-1">{dimensionLabel(name)}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* 优势 */}
        <Card>
          <CardHeader title="整体优势" description="值得在面试中重点展示" />
          {report?.strengths && report.strengths.length > 0 ? (
            <ul className="space-y-2">
              {report.strengths.map((s, i) => (
                <li key={i} className="flex gap-2 text-sm text-ink-2 leading-relaxed">
                  <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium text-ink-1">{dimensionLabel(s.dimension)}</span>
                    {s.detail && <span className="ml-1">— {s.detail}</span>}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-ink-3 py-4 text-center">暂无数据</div>
          )}
        </Card>

        {/* 短板 */}
        <Card>
          <CardHeader title="关键短板" description="影响整体评分，需重点突破" />
          {report?.improvements && report.improvements.length > 0 ? (
            <ul className="space-y-2">
              {report.improvements.map((s, i) => (
                <li key={i} className="flex gap-2 text-sm text-ink-2 leading-relaxed">
                  <AlertCircle className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium text-ink-1">{dimensionLabel(s.dimension)}</span>
                    {s.detail && <span className="ml-1">— {s.detail}</span>}
                    {s.suggestions && s.suggestions.length > 0 && (
                      <ul className="mt-1 space-y-0.5">
                        {s.suggestions.map((sg, j) => (
                          <li key={j} className="text-2xs text-ink-3 flex gap-1">
                            <span>•</span> {sg}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-ink-3 py-4 text-center">暂无数据</div>
          )}
        </Card>

        {/* 建议 */}
        <Card className="bg-gradient-to-br from-violet-50/40 to-surface dark:from-violet-500/5 dark:to-dark-surface border-violet-200/40 dark:border-violet-500/20">
          <CardHeader
            title={
              <div className="flex items-center gap-1.5">
                <Lightbulb className="h-3.5 w-3.5 text-violet-500" />
                提升建议
              </div>
            }
            description="基于本次表现生成"
          />
          {report?.summary_md ? (
            <div className="text-sm text-ink-2 leading-relaxed [&_p]:mb-2 [&_strong]:font-semibold">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.summary_md}</ReactMarkdown>
            </div>
          ) : (
            <div className="text-sm text-ink-3 py-4 text-center">暂无数据</div>
          )}
        </Card>
      </div>

      {/* 逐题复盘 */}
      <Card>
        <CardHeader
          title="逐题复盘"
          description="回顾每道题的回答与反馈"
          action={
            perQuestion.length > 0 ? (
              <button
                type="button"
                onClick={() => (allOpen ? collapseAll() : expandAll())}
                className="inline-flex items-center gap-1 text-xs text-ink-3 hover:text-ink-1 transition-colors px-2 py-1 rounded hover:bg-surface-muted dark:hover:bg-dark-surface-muted"
              >
                <ChevronsUpDown className="h-3.5 w-3.5" />
                {allOpen ? '全部收起' : '全部展开'}
              </button>
            ) : null
          }
        />
        {perQuestion.length === 0 ? (
          <div className="text-sm text-ink-3 py-8 text-center">暂无答题详情</div>
        ) : (
          <div className="-mx-1">
            {perQuestion.map((q) => {
              const isOpen = openSet.has(q.question_no)
              return (
                <div
                  key={q.question_no}
                  className="border-b border-surface-border dark:border-dark-surface-border last:border-b-0"
                >
                  <button
                    type="button"
                    onClick={() => toggle(q.question_no)}
                    aria-expanded={isOpen}
                    className="w-full flex items-center gap-3 px-3 py-3 rounded-md text-left hover:bg-surface-muted dark:hover:bg-dark-surface-muted transition-colors"
                  >
                    <div
                      className={cn(
                        'h-7 w-7 rounded-md flex items-center justify-center text-xs font-semibold flex-shrink-0',
                        tierBadge(q.score),
                      )}
                    >
                      {q.question_no}
                    </div>
                    <Badge variant="default" className="!h-4 flex-shrink-0">
                      {dimensionLabel(q.dimension)}
                    </Badge>
                    <span
                      className={cn(
                        'flex-1 min-w-0 truncate text-sm',
                        isOpen ? 'text-ink-1 font-medium' : 'text-ink-2',
                      )}
                    >
                      {q.question_text || '（无题目记录）'}
                    </span>
                    <span
                      className={cn(
                        'text-sm font-semibold tabular-nums flex-shrink-0',
                        tierText(q.score),
                      )}
                    >
                      {q.score}
                    </span>
                    <ChevronRight
                      className={cn(
                        'h-4 w-4 text-ink-3 flex-shrink-0 transition-transform duration-200',
                        isOpen && 'rotate-90 text-ink-2',
                      )}
                    />
                  </button>

                  <div
                    data-open={isOpen ? '' : undefined}
                    className="grid grid-rows-[0fr] data-[open]:grid-rows-[1fr] transition-[grid-template-rows] duration-300 ease-out"
                  >
                    <div className="overflow-hidden">
                      <div className="px-3 pb-4 pt-1 space-y-2">
                        <div className="rounded-md bg-surface-muted dark:bg-dark-surface-muted p-3">
                          <div className="text-2xs uppercase tracking-wider text-ink-3 font-medium mb-1.5">
                            题目
                          </div>
                          <div className="text-sm text-ink-1 leading-relaxed">
                            {q.question_text || '—'}
                          </div>
                        </div>
                        <div className="rounded-md bg-surface-muted dark:bg-dark-surface-muted p-3">
                          <div className="text-2xs uppercase tracking-wider text-ink-3 font-medium mb-1.5">
                            我的回答
                          </div>
                          <div className="text-sm text-ink-2 leading-relaxed whitespace-pre-wrap">
                            {q.user_answer || (
                              <span className="text-ink-3 italic">（未作答）</span>
                            )}
                          </div>
                        </div>
                        <div className="rounded-md bg-surface-muted dark:bg-dark-surface-muted p-3">
                          <div className="text-2xs uppercase tracking-wider text-ink-3 font-medium mb-1.5">
                            复盘点评
                          </div>
                          <div className="text-sm text-ink-2 leading-relaxed [&_p]:mb-1.5 [&_strong]:font-semibold [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5">
                            {q.feedback ? (
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {q.feedback}
                              </ReactMarkdown>
                            ) : (
                              '—'
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Card>
    </div>
  )
}
