/** 019 — Job detail panel with the two cross-module CTAs (US2/US3). */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, MessageSquare, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { JobsDetailBasicInfo } from '@/pages/Jobs'
import { useCreateInterviewFromJob } from '@/hooks/queries/useInterviewSessions'
import type { Job } from '@/repositories/JobRepository'

export function JobsDetailPanel({
  job,
  onClose,
}: {
  job: Job
  onClose?: () => void
}) {
  const navigate = useNavigate()
  const [startError, setStartError] = useState<string | null>(null)
  const createInterview = useCreateInterviewFromJob()
  const branchBound = !!job.branch_id
  const hasRequirements = !!(job.requirements_md && job.requirements_md.length > 0)

  async function startInterview() {
    if (!branchBound || !job.branch_id) return
    setStartError(null)
    try {
      const session = await createInterview.mutateAsync({
        jobId: job.id,
        branchId: job.branch_id,
      })
      navigate(`/interview/${session.id}`)
    } catch (err: any) {
      setStartError(err?.message || '创建面试失败')
    }
  }

  return (
    <div className="space-y-4" data-testid="job-detail-panel">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-ink-1">{job.company} · {job.position}</h2>
        {onClose && (
          <button onClick={onClose} className="text-xs text-ink-3 hover:text-ink-1" aria-label="关闭">×</button>
        )}
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
          onClick={() => navigate(`/resume?new=true&source_job_id=${job.id}`)}
        >
          为该岗位创建简历分支
        </Button>
      )}

      {/* 019 — US3 CTA: start mock interview (disabled until branch is bound) */}
      <Button
        variant={branchBound ? 'primary' : 'secondary'}
        leftIcon={
          createInterview.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <MessageSquare className="h-3.5 w-3.5" />
          )
        }
        data-testid="job-detail-interview-cta"
        disabled={!branchBound || createInterview.isPending}
        title={!branchBound ? '请先绑定简历分支' : '为该岗位开始模拟面试'}
        onClick={startInterview}
      >
        {createInterview.isPending ? '创建中…' : '为该岗位开始模拟面试'}
      </Button>
      {!branchBound && (
        <p className="text-2xs text-ink-3 -mt-3" data-testid="job-detail-interview-cta-hint">
          请先绑定简历分支
        </p>
      )}
      {startError && (
        <p className="text-2xs text-red-500 -mt-3" data-testid="job-detail-interview-cta-error">
          {startError}
        </p>
      )}
    </div>
  )
}
