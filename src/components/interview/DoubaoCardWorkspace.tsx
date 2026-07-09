import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, Copy, Loader2, RefreshCw } from 'lucide-react'
import { interviewSessionRepo, type InterviewSession } from '@/repositories/interviewSessionRepo'
import { useJob } from '@/hooks/queries/useJobs'
import { useResumeV2List } from '@/hooks/queries/useResumeV2List'
import { buildDoubaoPromptPayload } from '@/lib/doubaoPrompt'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'
import type { ResumeV2ListItem } from '@/modules/resume/v2/api'

export interface DoubaoCardWorkspaceProps {
  sessionId: string
  className?: string
  testId?: string
}

function fallbackResume(id: string | null | undefined): ResumeV2ListItem {
  return {
    id: id || 'unknown-resume',
    name: id ? '已选简历' : '未选择简历',
    slug: 'selected-resume',
    tags: [],
    is_public: false,
    is_locked: false,
    version: 1,
    created_at: null,
    updated_at: null,
  }
}

export function DoubaoCardWorkspace({
  sessionId,
  className,
  testId = 'doubao-card-workspace',
}: DoubaoCardWorkspaceProps) {
  const [copied, setCopied] = useState(false)

  const sessionQuery = useQuery<InterviewSession>({
    queryKey: ['interview-session', sessionId],
    queryFn: () => interviewSessionRepo.getById(sessionId),
    enabled: !!sessionId,
    staleTime: 30_000,
  })

  const session = sessionQuery.data
  const planQuery = useQuery({
    queryKey: ['interview-session-plan', sessionId],
    queryFn: () => interviewSessionRepo.generatePlan(sessionId),
    enabled: !!sessionId && !!session && !session.interview_plan,
    staleTime: 30_000,
  })
  const jobQuery = useJob(session?.job_id ?? '')
  const resumesQuery = useResumeV2List()

  const resume = useMemo(() => {
    const resumes = resumesQuery.data ?? []
    return resumes.find((item) => item.id === session?.branch_id) ?? fallbackResume(session?.branch_id)
  }, [resumesQuery.data, session?.branch_id])

  const plan = session?.interview_plan ?? planQuery.data?.data.interview_plan ?? null
  const job = jobQuery.data
  const payload = useMemo(() => {
    if (!job || !resume) return null
    return buildDoubaoPromptPayload(job, resume, plan, {
      questionCount: session?.max_questions ?? 10,
      scheduledAt: session?.created_at ?? null,
    })
  }, [job, plan, resume, session?.created_at, session?.max_questions])

  async function copyPrompt() {
    if (!payload) return
    await navigator.clipboard.writeText(payload.copyText)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  if (sessionQuery.isLoading || jobQuery.isLoading || resumesQuery.isLoading || planQuery.isLoading) {
    return (
      <section data-testid={testId} className={cn('flex min-h-64 items-center justify-center', className)}>
        <div className="flex items-center gap-2 text-sm text-ink-3">
          <Loader2 className="h-4 w-4 animate-spin" />
          准备豆包 Prompt
        </div>
      </section>
    )
  }

  if (!session || !job || !payload) {
    return (
      <section data-testid={testId} className={cn('rounded-md border border-line-2 bg-bg-1 p-6', className)}>
        <div className="flex items-start gap-3">
          <RefreshCw className="mt-0.5 h-4 w-4 text-ink-3" />
          <div>
            <h2 className="text-base font-semibold text-ink-1">Prompt 暂不可用</h2>
            <p className="mt-1 text-sm text-ink-3">未找到该面试关联的岗位或计划，请返回启动页重新创建。</p>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section
      data-testid={testId}
      data-mode="doubao"
      className={cn('mx-auto flex w-full max-w-[430px] flex-col gap-3 sm:max-w-[520px]', className)}
    >
      <header className="rounded-md border border-line-2 bg-bg-1 px-4 py-4 shadow-sm sm:px-5">
        <p className="text-xs font-medium text-ink-3">豆包模拟面试 Prompt</p>
        <h2 className="mt-1 text-xl font-semibold leading-tight text-ink-1 sm:text-2xl">{payload.title}</h2>
        <p className="mt-2 text-sm leading-6 text-ink-3">{payload.subtitle}</p>
        <Button
          type="button"
          variant="primary"
          size="md"
          className="mt-4 w-full"
          leftIcon={copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          onClick={copyPrompt}
          data-testid="doubao-copy-prompt"
        >
          {copied ? '已复制' : '复制 Prompt 到豆包'}
        </Button>
      </header>

      <div className="flex flex-col gap-3">
        {payload.sections.map((section, index) => (
          <PromptSection key={section.id} section={section} index={index + 1} />
        ))}
      </div>
    </section>
  )
}

function PromptSection({
  section,
  index,
}: {
  section: { id: string; title: string; content: string }
  index: number
}) {
  return (
    <article
      data-testid={`doubao-prompt-section-${section.id}`}
      className="rounded-md border border-line-2 bg-bg-1 px-4 py-4 shadow-sm sm:px-5"
    >
      <div className="mb-3 flex items-center gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-line-2 bg-bg-2 text-xs font-semibold tabular-nums text-ink-2">
          {index}
        </span>
        <h3 className="text-base font-semibold leading-tight text-ink-1">{section.title}</h3>
      </div>
      <div className="whitespace-pre-wrap break-words text-[15px] leading-7 text-ink-2 sm:text-base sm:leading-8">
        {section.content}
      </div>
    </article>
  )
}

export default DoubaoCardWorkspace
