import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  AlertCircle,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  ClipboardList,
  FileText,
  Loader2,
  MapPin,
  MessageSquare,
  Search,
  Sparkles,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { DrillCandidatesPreview } from '@/components/interview/DrillCandidatesPreview'
import { useInterviewModeStore, type InterviewMode } from '@/stores/useInterviewModeStore'
import { useJobs } from '@/hooks/queries/useJobs'
import { useResumeV2List } from '@/hooks/queries/useResumeV2List'
import { interviewSessionRepo, pollPlanStatus, resolvePlanStatus } from '@/repositories/interviewSessionRepo'
import type { Job } from '@/repositories/JobRepository'
import type { ResumeV2ListItem } from '@/modules/resume/v2/api'
import { cn } from '@/lib/utils'
import { request } from '@/api/client'

interface ErrorCountResponse {
  data: { available: number; required: number }
}

type OnlineMode = 'full' | 'quick_drill'
type LoadingStage = 'idle' | 'creating' | 'planning' | 'starting'

const EMPLOYMENT_TYPE_LABELS: Record<string, string> = {
  unspecified: '未指定',
  internship: '实习',
  campus: '校招',
  experienced: '社招',
  contract: '合同/外包',
  full_time: '全职',
  part_time: '兼职',
}

async function fetchErrorCount(): Promise<number> {
  try {
    const body = await request<ErrorCountResponse>('GET', '/api/v1/interview-sessions/mode-recommendation')
    return body.data?.available ?? 0
  } catch {
    return 0
  }
}

export function InterviewModeSelect() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const reset = useInterviewModeStore((s) => s.reset)
  const mode = useInterviewModeStore((s) => s.mode)
  const setMode = useInterviewModeStore((s) => s.setMode)
  const setSubMode = useInterviewModeStore((s) => s.setSubMode)
  const maxQuestions = useInterviewModeStore((s) => s.maxQuestions)
  const setMaxQuestions = useInterviewModeStore((s) => s.setMaxQuestions)
  const useVariants = useInterviewModeStore((s) => s.useVariants)
  const setUseVariants = useInterviewModeStore((s) => s.setUseVariants)

  const urlJobId = searchParams.get('job_id')
  const urlResumeId = searchParams.get('resume_id') || searchParams.get('branch_id')
  const jobsQuery = useJobs({ limit: 50 })
  const resumesQuery = useResumeV2List()
  const jobs = jobsQuery.data?.data ?? []
  const resumes = resumesQuery.data ?? []

  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedJobId, setSelectedJobId] = useState<string | null>(urlJobId)
  const [selectedResumeId, setSelectedResumeId] = useState<string | null>(urlResumeId)
  const [onlineMode, setOnlineMode] = useState<OnlineMode>('full')
  const [errorCount, setErrorCount] = useState<number | null>(null)
  const [quickDrillIds, setQuickDrillIds] = useState<string[]>([])
  const [showDrillPreview, setShowDrillPreview] = useState(false)
  const [loadingStage, setLoadingStage] = useState<LoadingStage>('idle')
  const [startError, setStartError] = useState<string | null>(null)

  useEffect(() => {
    reset()
    setMode('full')
    setSubMode('full')
    setMaxQuestions(10)
    setUseVariants(false)
  }, [reset, setMaxQuestions, setMode, setSubMode, setUseVariants])

  useEffect(() => {
    void fetchErrorCount().then(setErrorCount)
  }, [])

  useEffect(() => {
    if (!jobs.length) return
    setSelectedJobId((current) => {
      if (current && jobs.some((job) => job.id === current)) return current
      if (urlJobId && jobs.some((job) => job.id === urlJobId)) return urlJobId
      return jobs[0].id
    })
  }, [jobs, urlJobId])

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? null,
    [jobs, selectedJobId],
  )

  useEffect(() => {
    if (!resumes.length) return
    setSelectedResumeId((current) => {
      if (current && resumes.some((resume) => resume.id === current)) return current
      if (urlResumeId && resumes.some((resume) => resume.id === urlResumeId)) return urlResumeId
      if (selectedJob?.branch_id && resumes.some((resume) => resume.id === selectedJob.branch_id)) {
        return selectedJob.branch_id
      }
      return resumes[0].id
    })
  }, [resumes, selectedJob?.branch_id, urlResumeId])

  const selectedResume = useMemo(
    () => resumes.find((resume) => resume.id === selectedResumeId) ?? null,
    [resumes, selectedResumeId],
  )

  const statusOptions = useMemo(() => {
    const statuses = Array.from(new Set(jobs.map((job) => job.status).filter(Boolean)))
    return ['all', ...statuses]
  }, [jobs])

  const filteredJobs = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    return jobs.filter((job) => {
      const matchesStatus = statusFilter === 'all' || job.status === statusFilter
      const haystack = `${job.company} ${job.position} ${job.base_location || ''}`.toLowerCase()
      return matchesStatus && (!keyword || haystack.includes(keyword))
    })
  }, [jobs, query, statusFilter])

  const activeMode: InterviewMode = mode === 'doubao' ? 'doubao' : onlineMode
  const quickDrillDisabled = errorCount !== null && errorCount < 5
  const cannotStartReason = getCannotStartReason({
    job: selectedJob,
    resume: selectedResume,
    activeMode,
    quickDrillDisabled,
  })
  const isLoading = loadingStage !== 'idle'

  function selectOnline(next: OnlineMode) {
    setOnlineMode(next)
    setMode(next)
    setSubMode(next)
    if (next !== 'quick_drill') setQuickDrillIds([])
  }

  async function startInterview() {
    if (!selectedJob || !selectedResume || cannotStartReason) return
    setStartError(null)
    const requestMode: InterviewMode = activeMode
    try {
      setLoadingStage('creating')
      const created = await interviewSessionRepo.create({
        job_id: selectedJob.id,
        branch_id: selectedResume.id,
        mode: requestMode,
        max_questions: requestMode === 'full' ? maxQuestions ?? 10 : undefined,
        error_question_ids: requestMode === 'quick_drill' && quickDrillIds.length > 0 ? quickDrillIds : undefined,
        use_variants: requestMode === 'quick_drill' ? useVariants : false,
      })
      const sessionId = created.data.id

      if (requestMode === 'doubao') {
        setLoadingStage('planning')
        await interviewSessionRepo.generatePlan(sessionId)
      } else {
        setLoadingStage('starting')
        const started = await interviewSessionRepo.start(sessionId)
        if (requestMode === 'full') {
          setLoadingStage('planning')
          const startStatus = resolvePlanStatus({
            plan_status: started.data.plan_status,
            degraded: started.data.degraded,
            interview_plan: null,
          })
          const sess =
            startStatus === 'ready' || startStatus === 'failed' || startStatus === 'degraded'
              ? await interviewSessionRepo.getById(sessionId)
              : await pollPlanStatus(sessionId)
          const finalStatus = resolvePlanStatus(sess)
          if (finalStatus === 'failed' && sess.plan_error_message) {
            setStartError(sess.plan_error_message)
          }
        }
      }

      navigate(`/interview/${sessionId}/live`)
    } catch (err: any) {
      setStartError(err?.message || '启动模拟面试失败，请稍后重试。')
      setLoadingStage('idle')
    }
  }

  if (jobsQuery.isLoading || resumesQuery.isLoading) {
    return (
      <div className="flex h-full items-center justify-center bg-bg-2 p-6">
        <div className="flex items-center gap-2 text-sm text-ink-3">
          <Loader2 className="h-4 w-4 animate-spin" />
          正在加载岗位和简历
        </div>
      </div>
    )
  }

  if (jobsQuery.isError) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col items-center justify-center gap-4 p-8 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-md border border-red-200 bg-red-50">
          <AlertCircle className="h-5 w-5 text-red-600" />
        </div>
        <div data-testid="interview-job-load-error">
          <h1 className="text-xl font-semibold text-ink-1">岗位加载失败</h1>
          <p className="mt-2 text-sm text-ink-3">请稍后刷新重试，或先确认求职追踪服务是否可用。</p>
        </div>
      </div>
    )
  }

  if (!jobs.length) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col items-center justify-center gap-4 p-8 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-md border border-line-2 bg-bg-1">
          <BriefcaseBusiness className="h-5 w-5 text-ink-3" />
        </div>
        <div data-testid="interview-job-empty">
          <h1 className="text-xl font-semibold text-ink-1">先登记一个求职岗位</h1>
          <p className="mt-2 text-sm text-ink-3">模拟面试必须基于求职追踪里的岗位和原生 JD，不再支持手填目标岗位/公司。</p>
        </div>
        <Link to="/jobs?new=true">
          <Button variant="primary" leftIcon={<BriefcaseBusiness className="h-3.5 w-3.5" />}>
            去求职追踪创建岗位
          </Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto bg-bg-2 p-4 lg:p-6" data-testid="interview-launch-workbench">
      <div className="mx-auto flex max-w-[1440px] flex-col gap-4">
        <header className="flex flex-col gap-3 border-b border-line-2 pb-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-ink-1">模拟面试启动工作台</h1>
            <p className="mt-1 text-sm text-ink-3">选择求职追踪岗位和简历，再决定在线面试或复制豆包 Prompt。</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-ink-3">
            <StatusPill icon={<BriefcaseBusiness className="h-3 w-3" />} text={selectedJob ? '岗位已选' : '待选岗位'} ok={!!selectedJob} />
            <StatusPill icon={<FileText className="h-3 w-3" />} text={selectedResume ? '简历已选' : '待选简历'} ok={!!selectedResume} />
            <StatusPill icon={<ClipboardList className="h-3 w-3" />} text={activeMode === 'doubao' ? '豆包 Prompt' : activeMode === 'quick_drill' ? '错题补漏' : '完整面试'} ok />
          </div>
        </header>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
          <aside className="rounded-md border border-line-2 bg-bg-1 xl:min-h-[560px]" data-testid="interview-job-panel">
            <div className="border-b border-line-2 p-3">
              <div className="flex items-center gap-2 rounded-md border border-line-2 bg-bg-2 px-2 py-1.5">
                <Search className="h-3.5 w-3.5 text-ink-3" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="搜索公司、岗位、地点"
                  className="min-w-0 flex-1 bg-transparent text-sm text-ink-1 outline-none placeholder:text-ink-3"
                  data-testid="interview-job-search"
                />
              </div>
              <div className="mt-3 flex gap-2 overflow-x-auto" data-testid="interview-job-status-filter">
                {statusOptions.map((status) => (
                  <button
                    key={status}
                    type="button"
                    onClick={() => setStatusFilter(status)}
                    className={cn(
                      'shrink-0 rounded-md border px-2.5 py-1 text-xs',
                      statusFilter === status
                        ? 'border-brand-500 bg-brand-50 text-brand-700'
                        : 'border-line-2 bg-bg-1 text-ink-3 hover:text-ink-1',
                    )}
                  >
                    {status === 'all' ? '全部' : statusLabel(status)}
                  </button>
                ))}
              </div>
            </div>
            <div className="max-h-[360px] overflow-y-auto p-2 xl:max-h-[640px]" data-testid="interview-job-list">
              {filteredJobs.map((job) => (
                <JobOption
                  key={job.id}
                  job={job}
                  selected={job.id === selectedJobId}
                  onSelect={() => setSelectedJobId(job.id)}
                />
              ))}
              {!filteredJobs.length && (
                <p className="px-3 py-8 text-center text-sm text-ink-3">没有匹配的岗位</p>
              )}
            </div>
          </aside>

          <main className="rounded-md border border-line-2 bg-bg-1 p-4 xl:min-h-[560px]" data-testid="interview-context-panel">
            {selectedJob ? (
              <ContextPanel
                job={selectedJob}
                resumes={resumes}
                selectedResumeId={selectedResumeId}
                onResumeChange={setSelectedResumeId}
              />
            ) : (
              <p className="text-sm text-ink-3">请选择一个岗位。</p>
            )}
          </main>

          <aside className="rounded-md border border-line-2 bg-bg-1 p-4 xl:min-h-[560px]" data-testid="interview-mode-panel">
            <div className="space-y-5">
              <section>
                <h2 className="text-sm font-semibold text-ink-1">面试方式</h2>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <ModeButton
                    testId="mode-online"
                    active={mode !== 'doubao'}
                    icon={<MessageSquare className="h-4 w-4" />}
                    title="在线 AI 面试"
                    onClick={() => selectOnline(onlineMode)}
                  />
                  <ModeButton
                    testId="mode-doubao"
                    active={mode === 'doubao'}
                    icon={<Sparkles className="h-4 w-4" />}
                    title="豆包面试"
                    onClick={() => setMode('doubao')}
                  />
                </div>
              </section>

              {mode !== 'doubao' ? (
                <section>
                  <h2 className="text-sm font-semibold text-ink-1">在线模式</h2>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <ModeButton
                      testId="full-interview"
                      active={onlineMode === 'full'}
                      title="完整面试"
                      onClick={() => selectOnline('full')}
                    />
                    <ModeButton
                      testId="quick-drill"
                      active={onlineMode === 'quick_drill'}
                      title="错题补漏"
                      disabled={quickDrillDisabled}
                      onClick={() => {
                        selectOnline('quick_drill')
                        setShowDrillPreview(true)
                      }}
                    />
                  </div>
                  {onlineMode === 'full' ? (
                    <div className="mt-4">
                      <h3 className="text-xs font-medium text-ink-2">题量</h3>
                      <div className="mt-2 grid grid-cols-2 gap-2">
                        {[10, 15].map((count) => (
                          <button
                            key={count}
                            type="button"
                            data-testid={`full-interview-config-option-${count}`}
                            onClick={() => setMaxQuestions(count as 10 | 15)}
                            className={cn(
                              'rounded-md border px-3 py-2 text-left text-sm',
                              maxQuestions === count
                                ? 'border-brand-500 bg-brand-50 text-brand-700'
                                : 'border-line-2 bg-bg-2 text-ink-2 hover:text-ink-1',
                            )}
                          >
                            {count} 题
                            <span className="mt-1 block text-xs text-ink-3">{count === 10 ? '约 25 分钟' : '约 40 分钟'}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="mt-4 rounded-md border border-line-2 bg-bg-2 p-3 text-sm text-ink-2">
                      错题池：{errorCount ?? 0} / 5 可用
                      <p className="mt-1 text-xs text-ink-3">错题补漏会优先选择未掌握题，并围绕当前 JD 调整追问。</p>
                    </div>
                  )}
                </section>
              ) : (
                <section className="rounded-md border border-line-2 bg-bg-2 p-3">
                  <h2 className="text-sm font-semibold text-ink-1">豆包 Prompt 生成</h2>
                  <p className="mt-2 text-sm leading-6 text-ink-3">
                    启动后先生成 InterCraft 侧重点，再把原生 JD、考察侧重点和建议追问方向渲染成适合手机竖屏查看的 DOM Prompt 卡。
                  </p>
                </section>
              )}

              {resumes.length === 0 && (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800" data-testid="interview-resume-empty">
                  还没有可用简历。请先创建或导入简历后再启动模拟面试。
                  <Link to="/resume?new=true" className="ml-1 font-medium underline">去创建</Link>
                </div>
              )}

              {startError && (
                <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700" data-testid="interview-start-error">
                  {startError}
                </div>
              )}

              <Button
                type="button"
                variant="primary"
                size="lg"
                className="w-full"
                loading={isLoading}
                disabled={!!cannotStartReason || isLoading}
                onClick={startInterview}
                data-testid="interview-start-button"
              >
                {loadingLabel(loadingStage, activeMode)}
              </Button>
              {cannotStartReason && (
                <p className="text-xs text-ink-3" data-testid="interview-start-disabled-reason">{cannotStartReason}</p>
              )}
            </div>
          </aside>
        </div>
      </div>

      {showDrillPreview && selectedJob && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="drill-preview-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4"
          onClick={(event) => {
            if (event.target === event.currentTarget) setShowDrillPreview(false)
          }}
        >
          <h2 id="drill-preview-title" className="sr-only">错题补漏预览</h2>
          <DrillCandidatesPreview
            jdText={selectedJob.requirements_md || ''}
            onConfirm={(nextUseVariants, nextErrorQuestionIds) => {
              setUseVariants(nextUseVariants)
              setQuickDrillIds(nextErrorQuestionIds)
              setShowDrillPreview(false)
            }}
            onCancel={() => {
              setQuickDrillIds([])
              setShowDrillPreview(false)
              selectOnline('full')
            }}
          />
        </div>
      )}
    </div>
  )
}

function JobOption({ job, selected, onSelect }: { job: Job; selected: boolean; onSelect: () => void }) {
  const hasJd = !!job.requirements_md?.trim()
  return (
    <button
      type="button"
      onClick={onSelect}
      data-testid={`interview-job-option-${job.id}`}
      className={cn(
        'mb-2 w-full rounded-md border p-3 text-left transition',
        selected ? 'border-brand-500 bg-brand-50' : 'border-line-2 bg-bg-1 hover:bg-bg-2',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-ink-1">{job.position}</div>
          <div className="mt-1 flex items-center gap-1 truncate text-xs text-ink-3">
            <Building2 className="h-3 w-3" />
            {job.company}
          </div>
        </div>
        <span className={cn('shrink-0 rounded px-1.5 py-0.5 text-[11px]', hasJd ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700')}>
          {hasJd ? 'JD完整' : '缺JD'}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-ink-3">
        <span>{statusLabel(job.status)}</span>
        {job.base_location && (
          <span className="inline-flex items-center gap-0.5">
            <MapPin className="h-3 w-3" />
            {job.base_location}
          </span>
        )}
      </div>
    </button>
  )
}

function ContextPanel({
  job,
  resumes,
  selectedResumeId,
  onResumeChange,
}: {
  job: Job
  resumes: ResumeV2ListItem[]
  selectedResumeId: string | null
  onResumeChange: (id: string) => void
}) {
  return (
    <div className="grid h-full grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
      <section className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold text-ink-1">{job.company} · {job.position}</h2>
          <span className="rounded bg-bg-2 px-2 py-0.5 text-xs text-ink-3">{statusLabel(job.status)}</span>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2 text-sm text-ink-2 sm:grid-cols-2">
          <InfoRow label="地点" value={job.base_location || '未填写'} />
          <InfoRow label="薪资" value={job.salary_range_text || '未填写'} />
          <InfoRow
            label="类型"
            value={job.employment_type ? (EMPLOYMENT_TYPE_LABELS[job.employment_type] || job.employment_type) : '未填写'}
          />
          <InfoRow label="招聘人数" value={job.headcount ? `${job.headcount}` : '未填写'} />
        </div>
        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink-1">原生 JD</h3>
            <span className="text-xs text-ink-3">{job.requirements_md?.length ?? 0} 字</span>
          </div>
          <div className="max-h-[430px] overflow-y-auto rounded-md border border-line-2 bg-bg-2 p-3 text-sm leading-6 text-ink-2 whitespace-pre-wrap" data-testid="interview-job-jd">
            {job.requirements_md?.trim() || '该岗位还没有登记原生 JD。建议先回到求职追踪补充 JD，再启动定制模拟面试。'}
          </div>
        </div>
      </section>
      <aside className="rounded-md border border-line-2 bg-bg-2 p-3">
        <h3 className="text-sm font-semibold text-ink-1">面试简历</h3>
        <p className="mt-1 text-xs text-ink-3">岗位和简历共同构成面试上下文。</p>
        <select
          value={selectedResumeId ?? ''}
          onChange={(event) => onResumeChange(event.target.value)}
          disabled={!resumes.length}
          className="mt-3 w-full rounded-md border border-line-2 bg-bg-1 px-3 py-2 text-sm text-ink-1 outline-none disabled:cursor-not-allowed disabled:text-ink-3"
          data-testid="interview-resume-picker"
        >
          <option value="">{resumes.length ? '选择简历' : '暂无简历'}</option>
          {resumes.map((resume) => (
            <option key={resume.id} value={resume.id}>{resume.name}</option>
          ))}
        </select>
        <div className="mt-4 rounded-md border border-line-2 bg-bg-1 p-3">
          <div className="flex items-center gap-2 text-sm text-ink-2">
            {selectedResumeId ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <AlertCircle className="h-4 w-4 text-amber-600" />}
            {selectedResumeId ? '简历已绑定到本次面试' : '请选择一份简历'}
          </div>
        </div>
      </aside>
    </div>
  )
}

function ModeButton({
  active,
  disabled,
  icon,
  title,
  testId,
  onClick,
}: {
  active: boolean
  disabled?: boolean
  icon?: ReactNode
  title: string
  testId: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'flex min-h-16 items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50',
        active ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-line-2 bg-bg-2 text-ink-2 hover:text-ink-1',
      )}
    >
      {icon}
      {title}
    </button>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line-2 bg-bg-2 px-3 py-2">
      <div className="text-xs text-ink-3">{label}</div>
      <div className="mt-1 truncate text-sm text-ink-1">{value}</div>
    </div>
  )
}

function StatusPill({ icon, text, ok }: { icon: ReactNode; text: string; ok: boolean }) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded px-2 py-1', ok ? 'bg-emerald-50 text-emerald-700' : 'bg-bg-1 text-ink-3')}>
      {icon}
      {text}
    </span>
  )
}

function getCannotStartReason(args: {
  job: Job | null
  resume: ResumeV2ListItem | null
  activeMode: InterviewMode
  quickDrillDisabled: boolean
}): string | null {
  if (!args.job) return '请选择求职追踪里的岗位。'
  if (!args.resume) return '请选择一份简历。'
  if (args.activeMode === 'quick_drill' && args.quickDrillDisabled) return '错题池不足 5 题，暂不能启动错题补漏。'
  return null
}

function loadingLabel(stage: LoadingStage, mode: InterviewMode): string {
  if (stage === 'creating') return '正在创建 session'
  if (stage === 'planning') {
    return mode === 'doubao' ? '正在生成豆包 Prompt' : '正在生成面试计划'
  }
  if (stage === 'starting') return '正在准备对话'
  return mode === 'doubao' ? '生成豆包 Prompt' : '开始模拟面试'
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    interested: '感兴趣',
    applied: '已投递',
    screening: '筛选中',
    interviewing: '面试中',
    offer: 'Offer',
    rejected: '已拒绝',
    archived: '已归档',
  }
  return labels[status] ?? status
}

export default InterviewModeSelect
