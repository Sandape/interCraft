/**
 * REQ-053 (T069 + T071) — Full report viewer.
 *
 *  - Renders the report's `summary_md` as Markdown (6 chapters with emoji
 *    headings: 📋 🏢 📝 🎯 ⚠️ 💡) using the same `react-markdown` stack
 *    as InterviewReport.
 *  - Surfaces a delivery_status badge, a 1-5 star rating widget
 *    (interactive once a rating has not been submitted yet).
 *  - Parses the "📊 历史对比" section and renders it as a comparison table
 *    (T071). Falls back to "暂无历史对比数据" when missing.
 */
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  Calendar,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  Sparkles,
  Star,
  TrendingDown,
  TrendingUp,
  Minus,
  AlertCircle,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Card, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { useResearchReport, useResearchReports } from '@/hooks/queries/useResearchReports'
import { useRateResearchReport } from '@/hooks/mutations/useResearchReportMutations'
import type { DeliveryStatus } from '@/types/research'
import { cn } from '@/lib/utils'

// ─── Helpers ────────────────────────────────────────────────────────────────

const DELIVERY_BADGE: Record<
  DeliveryStatus,
  { label: string; variant: 'default' | 'brand' | 'success' | 'warning' | 'danger' | 'outline' }
> = {
  pending: { label: '发送中', variant: 'warning' },
  sent: { label: '已送达', variant: 'success' },
  failed: { label: '发送失败', variant: 'danger' },
  delayed: { label: '免打扰中', variant: 'default' },
}

// E2E tests assert `data-testid="research-report-section-${slug}"` — keep the
// slug stable in English so test selectors don't break when the zh-CN labels
// change. `title` is the on-screen label; `match` is the heading text the LLM
// may have used (with or without the leading emoji).
const SECTION_HEADINGS: Array<{ slug: string; emoji: string; title: string }> = [
  { slug: 'overview', emoji: '📋', title: '面试概览' },
  { slug: 'company', emoji: '🏢', title: '公司与产品速览' },
  { slug: 'experience', emoji: '📝', title: '面经汇总' },
  { slug: 'topics', emoji: '🎯', title: '高频考察点' },
  { slug: 'weakness', emoji: '⚠️', title: '你的薄弱环节' },
  { slug: 'tips', emoji: '💡', title: '最后建议' },
  { slug: 'comparison', emoji: '📊', title: '历史对比' },
]

/** Find a chapter slice (heading + body) inside the Markdown report. */
function findSection(md: string, heading: string): { title: string; body: string } | null {
  // 1) Find the heading line. We use `[ \t]*` (not `\s*`) so the
  //    trailing newline after the heading is not consumed — keeping the
  //    body slice anchored to the next line.
  // 2) Walk forward to the next `#` heading (or end of string) to bound
  //    the body. This is far more reliable than embedding both edges in
  //    a single regex, which interacted poorly with the `m` flag and
  //    `\Z` boundary.
  const headingRe = new RegExp(`^#{1,3}[ \\t]*${heading}[ \\t]*$`, 'm')
  const m = headingRe.exec(md)
  if (!m) return null
  const tail = md.slice(m.index + m[0].length)
  const next = /^[ \t]*#{1,3}[ \t]/m.exec(tail)
  const body = next ? tail.slice(0, next.index) : tail
  return { title: heading, body: body.trim() }
}

interface ComparisonRow {
  dimension: string
  last: string
  current: string
  trend: 'up' | 'down' | 'flat' | 'unknown'
}

/**
 * T071 — parse the "📊 历史对比" section. The expected shape (best-effort):
 *   | 维度 | 上次 | 本次 | 趋势 |
 *   | --- | --- | --- | --- |
 *   | tech_depth | 3.5 | 4.2 | ↑ |
 * Even when the report's authoring is loose (bullets, plain text), we
 * degrade gracefully to "暂无历史对比数据".
 */
function parseComparisonSection(body: string): ComparisonRow[] {
  if (!body) return []
  const lines = body.split(/\r?\n/)
  const rows: ComparisonRow[] = []
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed.startsWith('|')) continue
    const cells = trimmed
      .split('|')
      .map((c) => c.trim())
      .filter((c) => c.length > 0)
    if (cells.length < 4) continue
    // Skip header / separator rows.
    if (cells[0] === '维度' || /^[-:]+$/.test(cells[1] ?? '')) continue
    const trend = (cells[3] ?? '').trim()
    let t: ComparisonRow['trend'] = 'unknown'
    if (trend.includes('↑') || /up|上升|进步|改善/i.test(trend)) t = 'up'
    else if (trend.includes('↓') || /down|退步|下降/i.test(trend)) t = 'down'
    else if (trend.includes('→') || /flat|持平|不变/i.test(trend)) t = 'flat'
    rows.push({
      dimension: cells[0] ?? '',
      last: cells[1] ?? '',
      current: cells[2] ?? '',
      trend: t,
    })
  }
  return rows
}

function TrendIcon({ trend }: { trend: ComparisonRow['trend'] }) {
  if (trend === 'up') return <TrendingUp className="h-3 w-3 text-emerald-500" />
  if (trend === 'down') return <TrendingDown className="h-3 w-3 text-red-500" />
  if (trend === 'flat') return <Minus className="h-3 w-3 text-ink-3" />
  return <AlertCircle className="h-3 w-3 text-ink-3" />
}

// ─── Component ─────────────────────────────────────────────────────────────

export default function ResearchReportPage() {
  const params = useParams<{ jobId: string; reportId: string }>()
  const jobId = params.jobId ?? ''
  const reportId = params.reportId ?? ''
  const navigate = useNavigate()
  const { data: report, isLoading, isError, error } = useResearchReport(jobId, reportId)
  const { data: listData } = useResearchReports(jobId)
  const rateMutation = useRateResearchReport(jobId, reportId)
  const [hoveredStar, setHoveredStar] = useState<number | null>(null)

  const sections = useMemo(() => {
    if (!report?.summary_md) return []
    const out: { slug: string; emoji: string; title: string; body: string }[] = []
    for (const h of SECTION_HEADINGS) {
      const sec = findSection(report.summary_md, `${h.emoji} ${h.title}`)
      if (sec) {
        out.push({ slug: h.slug, emoji: h.emoji, title: h.title, body: sec.body })
      } else {
        // Fallback — heading may have been authored without the emoji prefix.
        const alt = findSection(report.summary_md, h.title)
        if (alt) out.push({ slug: h.slug, emoji: h.emoji, title: h.title, body: alt.body })
      }
    }
    return out
  }, [report?.summary_md])

  const comparisonRows = useMemo(() => {
    if (!report?.summary_md) return []
    const sec = findSection(report.summary_md, '📊 历史对比') ?? findSection(report.summary_md, '历史对比')
    if (!sec) return []
    return parseComparisonSection(sec.body)
  }, [report?.summary_md])

  if (isLoading) {
    return (
      <div
        data-testid="research-report-loading"
        className="h-full flex items-center justify-center min-h-[60vh]"
      >
        <Loader2 className="h-6 w-6 animate-spin text-ink-3" />
      </div>
    )
  }

  if (isError || !report) {
    return (
      <div className="px-8 py-10 max-w-3xl mx-auto" data-testid="research-report-error">
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<ArrowLeft className="h-3 w-3" />}
          onClick={() => navigate(-1)}
        >
          返回
        </Button>
        <Card className="mt-4 p-6 text-center">
          <AlertCircle className="h-6 w-6 text-red-500 mx-auto mb-2" />
          <div className="text-sm text-ink-1">报告加载失败</div>
          <div className="text-xs text-ink-3 mt-1">
            {error && typeof error === 'object' && 'message' in error
              ? String((error as { message: unknown }).message)
              : '请稍后重试'}
          </div>
        </Card>
      </div>
    )
  }

  const delivery = DELIVERY_BADGE[report.delivery_status] ?? DELIVERY_BADGE.pending
  const currentRating = report.rating ?? 0
  const listCount = listData?.data.length ?? 0

  return (
    <div
      className="px-8 py-6 max-w-3xl mx-auto"
      data-testid="research-report-page"
    >
      <div className="flex items-center justify-between mb-4">
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<ArrowLeft className="h-3 w-3" />}
          onClick={() => navigate(-1)}
          data-testid="research-report-back"
        >
          返回
        </Button>
        <Link
          to={`/jobs`}
          className="text-2xs text-ink-3 hover:text-ink-1"
          data-testid="research-report-jobs-link"
        >
          回到求职追踪 →
        </Link>
      </div>

      {/* ── Header card ────────────────────────────────────────────────── */}
      <Card className="p-5 mb-4" data-testid="research-report-header">
        <div className="flex items-start gap-3">
          <div className="h-10 w-10 rounded-md bg-brand-50 dark:bg-brand-500/10 flex items-center justify-center text-brand-600 dark:text-brand-300 flex-shrink-0">
            <Sparkles className="h-5 w-5" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-lg font-semibold text-ink-1">面试备战报告</div>
            <div className="text-xs text-ink-3 mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="inline-flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {new Date(report.interview_time).toLocaleString('zh-CN')}
              </span>
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3 w-3" />
                生成于 {new Date(report.generated_at).toLocaleString('zh-CN')}
              </span>
              {report.delivered_at && (
                <span className="inline-flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  送达于 {new Date(report.delivered_at).toLocaleString('zh-CN')}
                </span>
              )}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <Badge variant={delivery.variant} data-testid="research-report-delivery-badge">
              {delivery.label}
            </Badge>
            {report.quality_check_passed === false && (
              <Badge variant="warning">质量校验未通过</Badge>
            )}
          </div>
        </div>
      </Card>

      {/* ── T070 — sibling reports indicator ─────────────────────────── */}
      {listCount > 1 && (
        <div
          data-testid="research-report-sibling-count"
          className="mb-4 text-2xs text-ink-3"
        >
          该岗位共有 {listCount} 份报告，当前展示最早生成的一份。
        </div>
      )}

      {/* ── Body — 6 chapters (T069) ─────────────────────────────────── */}
      {sections.length === 0 ? (
        <Card className="p-4" data-testid="research-report-body-fallback">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {report.summary_md}
          </ReactMarkdown>
        </Card>
      ) : (
        <div className="space-y-4" data-testid="research-report-body">
          {sections
            .filter((s) => s.slug !== 'comparison')
            .map((s) => (
              <Card key={s.slug} className="p-4" data-testid={`research-report-section-${s.slug}`}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-base" aria-hidden>
                    {s.emoji}
                  </span>
                  <h2 className="text-sm font-semibold text-ink-1">{s.title}</h2>
                </div>
                <div className="text-sm text-ink-2 leading-relaxed [&_p]:mb-2 [&_strong]:font-semibold [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mb-1 [&_h1]:hidden [&_h2]:hidden [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mt-3 [&_code]:bg-surface-muted [&_code]:px-1 [&_code]:rounded">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {s.body}
                  </ReactMarkdown>
                </div>
              </Card>
            ))}
        </div>
      )}

      {/* ── T071 — Historical comparison table ─────────────────────── */}
      <Card className="p-4 mt-4" data-testid="research-report-comparison">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-base" aria-hidden>
            📊
          </span>
          <h2 className="text-sm font-semibold text-ink-1">历史对比</h2>
        </div>
        {comparisonRows.length === 0 ? (
          <div
            className="text-xs text-ink-3"
            data-testid="research-report-comparison-empty"
          >
            暂无历史对比数据
          </div>
        ) : (
          <div className="overflow-x-auto" data-testid="research-report-comparison-table">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-2xs text-ink-3 uppercase tracking-wider border-b border-surface-border dark:border-dark-surface-border">
                  <th className="px-2 py-1.5 font-medium">维度</th>
                  <th className="px-2 py-1.5 font-medium">上次</th>
                  <th className="px-2 py-1.5 font-medium">本次</th>
                  <th className="px-2 py-1.5 font-medium">趋势</th>
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map((row, i) => (
                  <tr
                    key={`${row.dimension}-${i}`}
                    className="border-b border-surface-border dark:border-dark-surface-border last:border-0"
                  >
                    <td className="px-2 py-1.5 text-ink-1">{row.dimension}</td>
                    <td className="px-2 py-1.5 text-ink-2">{row.last}</td>
                    <td className="px-2 py-1.5 text-ink-1 font-medium">{row.current}</td>
                    <td className="px-2 py-1.5">
                      <span className="inline-flex items-center gap-1">
                        <TrendIcon trend={row.trend} />
                        <span className="text-ink-3">
                          {row.trend === 'up'
                            ? '进步'
                            : row.trend === 'down'
                              ? '退步'
                              : row.trend === 'flat'
                                ? '持平'
                                : '—'}
                        </span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ── Rating widget (SC-009) ──────────────────────────────────── */}
      <Card className="p-4 mt-4" data-testid="research-report-rating">
        <CardHeader
          title="这份报告对你有帮助吗？"
          description="1-5 星评分会用于驱动报告质量的持续改进"
        />
        <div className="flex items-center gap-3">
          <div
            className="inline-flex items-center"
            data-testid="research-report-rating-stars"
            onMouseLeave={() => setHoveredStar(null)}
          >
            {[1, 2, 3, 4, 5].map((n) => {
              const filled = (hoveredStar ?? currentRating) >= n
              return (
                <button
                  key={n}
                  type="button"
                  data-testid={`research-report-star-${n}`}
                  onMouseEnter={() => setHoveredStar(n)}
                  onClick={() => rateMutation.mutate(n)}
                  disabled={rateMutation.isPending}
                  className={cn(
                    'p-0.5 rounded transition-transform',
                    !rateMutation.isPending && 'hover:scale-110',
                  )}
                  aria-label={`评分 ${n} 星`}
                >
                  <Star
                    className={cn(
                      'h-5 w-5',
                      filled
                        ? 'fill-amber-400 text-amber-400'
                        : 'text-ink-3',
                    )}
                  />
                </button>
              )
            })}
          </div>
          <span
            className="text-xs text-ink-2"
            data-testid="research-report-rating-current"
          >
            {currentRating > 0 ? `当前评分 ${currentRating}/5` : '尚未评分'}
          </span>
          {rateMutation.isPending && (
            <Loader2 className="h-3 w-3 animate-spin text-ink-3" />
          )}
          {rateMutation.isError && (
            <span className="text-2xs text-red-500">提交失败</span>
          )}
        </div>
      </Card>
    </div>
  )
}
