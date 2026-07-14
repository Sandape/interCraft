import { ArrowLeft, ArrowRight, Check, FileText, ListChecks, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input, Textarea } from '@/components/ui/Input'
import type {
  JobSearchStage,
  OnboardingState,
  ResumeEntryMode,
  TargetEntryMode,
} from './onboarding-state'
import { cn } from '@/lib/utils'

const stages: Array<{ id: JobSearchStage; label: string }> = [
  { id: 'campus', label: '校招' },
  { id: 'experienced', label: '社招' },
  { id: 'internship', label: '实习' },
  { id: 'career_switch', label: '转行' },
  { id: 'exploring', label: '探索中' },
]

const templates = ['产品经理', 'Java 后端', '数据分析师', '内容运营', '财务分析', '管理培训生'] as const

export function GoalStep({
  state,
  error,
  onChange,
  onNext,
}: StepProps & { onNext: () => void }) {
  return (
    <StepFrame eyebrow="Step 01 · Job goal" title="你这次想争取什么机会？" body="先告诉 InterCraft 你要赢下什么，再开始整理简历。">
      <fieldset>
        <legend className="text-xs font-semibold text-ink-1">求职阶段</legend>
        <div className="mt-3 flex flex-wrap gap-2">
          {stages.map((stage) => (
            <button
              key={stage.id}
              type="button"
              className={cn('onboarding-choice', state.goal.stage === stage.id && 'is-selected')}
              aria-pressed={state.goal.stage === stage.id}
              onClick={() => onChange({ ...state, goal: { ...state.goal, stage: stage.id } })}
            >
              {stage.label}
            </button>
          ))}
        </div>
      </fieldset>
      <div className="mt-7 grid gap-5 sm:grid-cols-2">
        <label className="block">
          <span className="text-xs font-semibold text-ink-1">目标岗位或方向 <span className="text-red-600">*</span></span>
          <Input
            size="lg"
            className="mt-2"
            value={state.goal.targetRole}
            maxLength={120}
            onChange={(event) => onChange({ ...state, goal: { ...state.goal, targetRole: event.target.value } })}
            placeholder="例如：产品经理、数据分析"
            aria-label="目标岗位或方向"
          />
        </label>
        <label className="block">
          <span className="text-xs font-semibold text-ink-1">目标城市（可选）</span>
          <Input
            size="lg"
            className="mt-2"
            value={state.goal.city}
            maxLength={80}
            onChange={(event) => onChange({ ...state, goal: { ...state.goal, city: event.target.value } })}
            placeholder="例如：上海、远程"
          />
        </label>
      </div>
      <StepActions error={error} onNext={onNext} />
    </StepFrame>
  )
}

export function BaselineStep({
  state,
  error,
  persistPending = false,
  persistFailed = false,
  onChange,
  onBack,
  onNext,
  onRetry,
}: StepProps & NavigationProps & {
  persistPending?: boolean
  persistFailed?: boolean
  onRetry?: () => void
}) {
  const choices: Array<{ id: ResumeEntryMode; title: string; detail: string }> = [
    { id: 'paste', title: '粘贴现有内容', detail: '适合已有简历或经历笔记' },
    { id: 'structured', title: '逐步填写', detail: '先写核心经历，之后再完善' },
    { id: 'blank', title: '从空白草稿开始', detail: '先建立资产，稍后补充内容' },
  ]
  const submitDisabled = persistPending
  return (
    <StepFrame eyebrow="Step 02 · Baseline resume" title="创建根简历草稿" body="它是可持续补充的职业素材库，不需要现在就写成完美终稿。">
      <fieldset>
        <legend className="text-xs font-semibold text-ink-1">选择起步方式</legend>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          {choices.map((choice) => (
            <button
              key={choice.id}
              type="button"
              className={cn('onboarding-option text-left', state.baseline.entryMode === choice.id && 'is-selected')}
              aria-pressed={state.baseline.entryMode === choice.id}
              onClick={() => onChange({ ...state, baseline: { ...state.baseline, entryMode: choice.id } })}
              disabled={persistPending}
            >
              <FileText className="h-4 w-4 text-ink-3" />
              <span className="mt-3 block text-xs font-semibold text-ink-1">{choice.title}</span>
              <span className="mt-1 block text-2xs leading-5 text-ink-3">{choice.detail}</span>
            </button>
          ))}
        </div>
      </fieldset>
      {state.baseline.entryMode === '' ? (
        <div className="onboarding-empty mt-6 text-center">
          <FileText className="mx-auto h-5 w-5 text-ink-muted" />
          <p className="mt-2 text-xs text-ink-3">选择一种方式后继续。不会解析 PDF，也不会自动虚构经历。</p>
        </div>
      ) : state.baseline.entryMode === 'blank' ? (
        <div className="mt-6 border-l-2 border-brand-900 bg-surface-subtle px-4 py-3 text-xs leading-6 text-ink-2">
          已选择空白根简历草稿。下一步会向服务端发送一份完整 v2 简历，源码区严格为空。
        </div>
      ) : (
        <label className="mt-6 block">
          <span className="text-xs font-semibold text-ink-1">
            {state.baseline.entryMode === 'paste' ? '简历内容或经历笔记' : '先写一段核心经历'}
          </span>
          <Textarea
            size="lg"
            className="mt-2 min-h-40"
            value={state.baseline.content}
            maxLength={20000}
            disabled={persistPending}
            onChange={(event) => onChange({ ...state, baseline: { ...state.baseline, content: event.target.value } })}
            placeholder="例如：负责某项产品从调研到上线，推动关键指标从……"
          />
          <span className="mt-1 block text-2xs text-ink-3">至少写下一个真实经历线索；之后可以继续完善。</span>
        </label>
      )}
      <StepActions
        error={error}
        onBack={onBack}
        onNext={onNext}
        nextLabel={persistPending ? '正在保存根简历…' : '下一步'}
        loading={persistPending}
        disabled={submitDisabled}
        onRetry={persistFailed && onRetry ? onRetry : undefined}
      />
    </StepFrame>
  )
}

export function TargetStep({ state, error, onChange, onBack, onNext }: StepProps & NavigationProps) {
  const chooseMode = (mode: TargetEntryMode) => onChange({ ...state, target: { ...state.target, mode } })
  return (
    <StepFrame eyebrow="Step 03 · Target job" title="添加一个目标岗位" body="有具体 JD 就粘贴；还在探索，也可以先选一个岗位起步模板。">
      <div className="grid gap-2 sm:grid-cols-2">
        <button type="button" className={cn('onboarding-option text-left', state.target.mode === 'jd' && 'is-selected')} aria-pressed={state.target.mode === 'jd'} onClick={() => chooseMode('jd')}>
          <ListChecks className="h-4 w-4 text-ink-3" />
          <span className="mt-3 block text-xs font-semibold text-ink-1">我有具体 JD</span>
          <span className="mt-1 block text-2xs text-ink-3">粘贴职责和要求，不上传文件</span>
        </button>
        <button type="button" className={cn('onboarding-option text-left', state.target.mode === 'template' && 'is-selected')} aria-pressed={state.target.mode === 'template'} onClick={() => chooseMode('template')}>
          <Sparkles className="h-4 w-4 text-ink-3" />
          <span className="mt-3 block text-xs font-semibold text-ink-1">先选岗位模板</span>
          <span className="mt-1 block text-2xs text-ink-3">使用前端 Demo 模板完成流程</span>
        </button>
      </div>
      {state.target.mode === 'jd' && (
        <label className="mt-6 block">
          <span className="text-xs font-semibold text-ink-1">岗位描述</span>
          <Textarea size="lg" className="mt-2 min-h-44" value={state.target.jd} maxLength={30000} onChange={(event) => onChange({ ...state, target: { ...state.target, jd: event.target.value } })} placeholder="粘贴岗位职责、任职要求和加分项……" />
          <span className="mt-1 block text-2xs text-ink-3">建议保留完整职责与任职要求，至少 40 个字符。</span>
        </label>
      )}
      {state.target.mode === 'template' && (
        <fieldset className="mt-6">
          <legend className="text-xs font-semibold text-ink-1">岗位起步模板</legend>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {templates.map((template) => (
              <button key={template} type="button" className={cn('onboarding-choice justify-between', state.target.templateId === template && 'is-selected')} aria-pressed={state.target.templateId === template} onClick={() => onChange({ ...state, target: { ...state.target, templateId: template } })}>
                {template}{state.target.templateId === template && <Check className="h-3.5 w-3.5" />}
              </button>
            ))}
          </div>
        </fieldset>
      )}
      <StepActions error={error} onBack={onBack} onNext={onNext} nextLabel="检查并生成" />
    </StepFrame>
  )
}

export function GenerateStep({
  state,
  error,
  loading,
  onBack,
  onGenerate,
}: {
  state: OnboardingState
  error: string | null
  loading: boolean
  onBack: () => void
  onGenerate: () => void
}) {
  return (
    <StepFrame eyebrow="Step 04 · First tailored resume" title="生成第一份岗位定制简历" body="确认上下文后生成 Demo 结果：匹配分析、能力差距和优化建议会一起出现。">
      <div className="grid gap-px overflow-hidden border border-surface-border bg-surface-border sm:grid-cols-3">
        <ReviewItem label="求职目标" value={state.goal.targetRole} />
        <ReviewItem label="根简历" value={state.baseline.entryMode === 'blank' ? '空白草稿' : '已有经历内容'} />
        <ReviewItem label="目标岗位" value={state.target.mode === 'template' ? state.target.templateId : '已粘贴 JD'} />
      </div>
      <div className="mt-6 border-l-2 border-amber-500 bg-amber-50 px-4 py-3 text-xs leading-6 text-amber-900">
        P0 使用明确的 Demo 分析结果，不会调用真实 AI，也不会将结果伪装为真实岗位分析。
      </div>
      <StepActions error={error} onBack={onBack} onNext={onGenerate} nextLabel="生成 Demo 岗位定制简历" loading={loading} disabled={loading} />
    </StepFrame>
  )
}

function StepFrame({ eyebrow, title, body, children }: { eyebrow: string; title: string; body: string; children: React.ReactNode }) {
  return (
    <div className="onboarding-step-panel">
      <p className="text-2xs font-semibold uppercase tracking-[0.16em] text-brand-600">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-semibold tracking-[-0.025em] text-ink-1">{title}</h2>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-ink-3">{body}</p>
      <div className="mt-8">{children}</div>
    </div>
  )
}

function StepActions({
  error,
  onBack,
  onNext,
  nextLabel = '下一步',
  loading,
  disabled,
  onRetry,
}: {
  error: string | null
  onBack?: () => void
  onNext: () => void
  nextLabel?: string
  loading?: boolean
  disabled?: boolean
  /**
   * When the previous step failed (e.g. POST /v2/resumes/root returned
   * a 5xx), surface a focused retry button instead of the next button so
   * the user can re-attempt without losing the form state.
   */
  onRetry?: () => void
}) {
  const nextLabelText = loading ? (nextLabel && nextLabel !== '下一步' ? nextLabel : '正在生成 Demo…') : nextLabel
  return (
    <div className="mt-8 border-t border-surface-border pt-5">
      {error && (
        <div role="alert" className="mb-4 rounded bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="ml-3 underline"
              data-testid="onboarding-baseline-retry"
            >
              重试
            </button>
          )}
        </div>
      )}
      <div className="flex items-center justify-between gap-3">
        {onBack ? (
          <Button
            type="button"
            size="lg"
            variant="ghost"
            className="min-h-11"
            leftIcon={<ArrowLeft className="h-4 w-4" />}
            onClick={onBack}
            disabled={disabled}
          >
            上一步
          </Button>
        ) : (
          <span />
        )}
        <Button
          type="button"
          size="lg"
          variant="primary"
          className="min-h-11 px-5"
          data-testid="onboarding-baseline-next"
          rightIcon={<ArrowRight className="h-4 w-4" />}
          onClick={onNext}
          loading={loading}
          disabled={disabled}
        >
          {nextLabelText}
        </Button>
      </div>
    </div>
  )
}

function ReviewItem({ label, value }: { label: string; value: string }) {
  return <div className="bg-surface p-4"><div className="text-2xs text-ink-3">{label}</div><div className="mt-1 text-sm font-medium text-ink-1">{value}</div></div>
}

interface StepProps {
  state: OnboardingState
  error: string | null
  onChange: (state: OnboardingState) => void
}

interface NavigationProps {
  onBack: () => void
  onNext: () => void
}
