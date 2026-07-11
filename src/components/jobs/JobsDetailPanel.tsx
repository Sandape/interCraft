/** 019 — Job detail panel with the two cross-module CTAs (US2/US3).
 *  REQ-053 (T068) — adds a "查看备战报告" entry when an interview time
 *  is set AND a research report exists for the job.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Calendar,
  ExternalLink,
  FileText,
  History,
  Loader2,
  MessageSquare,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { JobsDetailBasicInfo } from '@/pages/Jobs'
import { InterviewTimeRow } from '@/components/jobs/JobTimeline'
import { useResearchReports } from '@/hooks/queries/useResearchReports'
import { useBindBranchToJob } from '@/hooks/mutations/useJobMutations'
import { useQueryClient } from '@tanstack/react-query'
import type { Job } from '@/repositories/JobRepository'
import { listJobDerivedResumes } from '@/modules/resume/derive/api'

/**
 * REQ-053 (T070) — when the user has multiple reports (multi-round interviews),
 * list the most recent first with a "查看" link per row.
 */
function ResearchReportHistoryList({ jobId }: { jobId: string }) {
  const navigate = useNavigate()
  const { data, isLoading } = useResearchReports(jobId)
  const reports = data?.data ?? []
  if (isLoading) {
    return (
      <div className="text-2xs text-ink-3 flex items-center gap-1.5" data-testid="research-reports-loading">
        <Loader2 className="h-3 w-3 animate-spin" /> 加载报告列表…
      </div>
    )
  }
  if (reports.length === 0) {
    return (
      <div className="text-2xs text-ink-3" data-testid="research-reports-empty">
        暂无面试备战报告
      </div>
    )
  }
  // API contract: sorted by interview_time DESC. Re-sort defensively.
  const ordered = [...reports].sort(
    (a, b) => new Date(b.interview_time).getTime() - new Date(a.interview_time).getTime(),
  )
  return (
    <div className="space-y-1.5" data-testid="research-reports-history">
      {ordered.map((r) => (
        <button
          key={r.id}
          type="button"
          data-testid={`research-report-link-${r.id}`}
          onClick={() => navigate(`/research-reports/${jobId}/${r.id}`)}
          className="w-full text-left flex items-center gap-2 rounded-md border border-surface-border dark:border-dark-surface-border px-2.5 py-1.5 text-xs hover:bg-surface-muted dark:hover:bg-dark-surface-muted"
        >
          <History className="h-3 w-3 text-ink-3 flex-shrink-0" />
          <span className="font-medium text-ink-1 flex-1 min-w-0 truncate">
            {new Date(r.interview_time).toLocaleString('zh-CN')}
          </span>
          <span className="text-2xs text-ink-3">评分 {r.rating ?? '—'}/5</span>
          <ExternalLink className="h-3 w-3 text-ink-3 flex-shrink-0" />
        </button>
      ))}
    </div>
  )
}

export function JobsDetailPanel({
  job,
  onClose,
}: {
  job: Job
  onClose?: () => void
}) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const bindBranch = useBindBranchToJob()
  const branchBound = !!job.branch_id
  const hasRequirements = !!(job.requirements_md && job.requirements_md.length > 0)

  // REQ-053 (T068) — gate the entry button on interview_time set + a report
  // existing. `useResearchReports` returns [] when the backend has no row,
  // so we treat "non-empty list" as `has_research_report === true`.
  const { data: reportsData } = useResearchReports(job.id)
  const reports = reportsData?.data ?? []
  const latestReport = reports[0] ?? null
  const hasResearchReport =
    !!job.interview_time && !!latestReport
  const showReportHistory = reports.length > 1

  function startInterview() {
    if (!branchBound || !job.branch_id) return
    // Route into the mode-selection workbench with job/resume prefilled.
    // Creating the session here skipped REQ-048 mode choice (full / quick_drill / doubao).
    navigate(
      `/interview/mode?job_id=${encodeURIComponent(job.id)}&branch_id=${encodeURIComponent(job.branch_id)}`,
    )
  }

  function openLatestReport() {
    if (!latestReport) return
    // Invalidate so the detail page always re-fetches on entry.
    qc.invalidateQueries({ queryKey: ['researchReport', job.id, latestReport.id] })
    navigate(`/research-reports/${job.id}/${latestReport.id}`)
  }

  return (
    <div className="space-y-4" data-testid="job-detail-panel">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-ink-1">
          {job.company} · {job.position}
        </h2>
        {onClose && (
          <button
            onClick={onClose}
            className="text-xs text-ink-3 hover:text-ink-1"
            aria-label="关闭"
          >
            ×
          </button>
        )}
      </div>

      {/* REQ-053 (T028) — interview time surfaces right under the title. */}
      <div
        data-testid="job-detail-interview-time"
        className="rounded-md bg-surface-muted/60 dark:bg-dark-surface-muted/40 px-3 py-2"
      >
        <div className="flex items-center gap-2 text-2xs text-ink-3 mb-1">
          <Calendar className="h-3 w-3" />
          <span>面试时间</span>
        </div>
        <InterviewTimeRow interviewTime={job.interview_time} />
      </div>

      {/* 019 — basic info with the 5 extended fields */}
      <JobsDetailBasicInfo job={job} />

      {/* 019 — bound branch (FR-008: clickable to resume editor) */}
      <div className="text-xs flex items-baseline gap-2 pt-1 border-t border-surface-border dark:border-dark-surface-border">
        <span className="text-ink-3 w-20 flex-shrink-0">绑定的简历分支</span>
        {branchBound ? (
          <button
            type="button"
            data-testid="job-detail-bound-branch"
            onClick={() => navigate(`/resume/${job.branch_id}`)}
            className="text-brand-600 dark:text-brand-300 hover:underline truncate"
          >
            查看/编辑该分支
          </button>
        ) : (
          <span className="text-ink-3">(无)</span>
        )}
      </div>

      {/* 019 — US2 CTA: create resume branch from this job */}
      {!branchBound && (
        <Button
          variant="primary"
          leftIcon={<FileText className="h-3.5 w-3.5" />}
          data-testid="job-detail-resume-cta"
          onClick={() => navigate(`/resume?derive=true&job_id=${job.id}`)}
        >
          为该岗位创建简历分支
        </Button>
      )}

      {/* REQ-055 — derived resumes bound to this job */}
      <JobDerivedResumesSection
        jobId={job.id}
        boundBranchId={job.branch_id ?? null}
        hasRequirements={hasRequirements}
        isBinding={bindBranch.isPending}
        onBind={(branchId) => bindBranch.mutate({ jobId: job.id, branchId })}
      />

      {/* REQ-053 (T068) — report entry is gated on interview_time + report existence. */}
      {hasResearchReport && (
        <Button
          variant="primary"
          leftIcon={<FileText className="h-3.5 w-3.5" />}
          data-testid="job-detail-research-report-cta"
          onClick={openLatestReport}
        >
          查看备战报告
        </Button>
      )}

      {/* 019 — US3 CTA: start mock interview (disabled until branch is bound) */}
      <Button
        variant={branchBound ? 'primary' : 'secondary'}
        leftIcon={<MessageSquare className="h-3.5 w-3.5" />}
        data-testid="job-detail-interview-cta"
        disabled={!branchBound}
        title={!branchBound ? '请先绑定简历分支' : '为该岗位开始模拟面试'}
        onClick={startInterview}
      >
        为该岗位开始模拟面试
      </Button>
      {!branchBound && (
        <p className="text-2xs text-ink-3 -mt-3" data-testid="job-detail-interview-cta-hint">
          请先绑定简历分支
        </p>
      )}

      {/* REQ-053 (T070) — multi-round history list. Only shown when > 1. */}
      {showReportHistory && (
        <Card padding="sm" data-testid="job-detail-report-history-card">
          <CardHeader
            title="历史备战报告"
            description="按面试时间倒序排列，点击进入详情"
          />
          <ResearchReportHistoryList jobId={job.id} />
        </Card>
      )}
    </div>
  )
}

function JobDerivedResumesSection({
  jobId,
  boundBranchId,
  hasRequirements,
  isBinding,
  onBind,
}: {
  jobId: string
  boundBranchId: string | null
  hasRequirements: boolean
  isBinding: boolean
  onBind: (branchId: string) => void
}) {
  const navigate = useNavigate()
  const [items, setItems] = useState<Array<Record<string, unknown>>>([])

  useEffect(() => {
    let cancelled = false
    listJobDerivedResumes(jobId)
      .then((r) => {
        if (!cancelled) setItems(r.data || [])
      })
      .catch(() => {
        if (!cancelled) setItems([])
      })
    return () => {
      cancelled = true
    }
  }, [jobId])

  return (
    <div className="space-y-2 border-t border-surface-border pt-2" data-testid="job-derived-resumes">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-ink-3">派生简历（REQ-055）</span>
        <Button
          size="sm"
          variant="secondary"
          disabled={!hasRequirements}
          title={hasRequirements ? undefined : '请先补充 JD'}
          onClick={() => navigate(`/resume?derive=true&job_id=${jobId}`)}
        >
          一键派生
        </Button>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-ink-3">暂无派生简历</p>
      ) : (
        <ul className="space-y-1 text-xs">
          {items.map((it) => (
            <li key={String(it.id)}>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left text-brand-600 hover:underline"
                  onClick={() => navigate(`/resume/${String(it.id)}`)}
                >
                {String(it.name)} · 目标 {String(it.target_page_count ?? '—')} 页 / 实际{' '}
                {String(it.actual_page_count ?? '—')} 页
                </button>
                {boundBranchId === String(it.id) ? (
                  <span
                    className="rounded border border-brand-200 bg-brand-50 px-2 py-0.5 text-2xs text-brand-700"
                    data-testid={`job-derived-resume-bound-${String(it.id)}`}
                  >
                    已绑定
                  </span>
                ) : (
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={isBinding}
                    data-testid={`job-derived-resume-bind-${String(it.id)}`}
                    onClick={() => onBind(String(it.id))}
                  >
                    绑定
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
