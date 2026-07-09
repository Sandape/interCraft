import { ChevronDown, ChevronUp, ExternalLink, ListChecks, Search, Target } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { InterviewPlan, InterviewWebResearch, WebResearchResult } from '@/repositories/interviewSessionRepo'

interface InterviewPlanPanelProps {
  plan: InterviewPlan | null | undefined
  webResearch?: InterviewWebResearch | null
  open?: boolean
  onToggle?: () => void
  className?: string
  compact?: boolean
  testId?: string
}

const difficultyLabel: Record<string, string> = {
  easy: '轻松',
  medium: '标准',
  hard: '高压',
}

function asArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : []
}

function collectSources(webResearch: InterviewWebResearch | null | undefined): WebResearchResult[] {
  if (!webResearch) return []
  return [
    ...asArray(webResearch.interview_experience),
    ...asArray(webResearch.company_tech_stack),
    ...asArray(webResearch.common_questions),
  ].filter((item) => item && (item.title || item.url || item.content))
}

export function InterviewPlanPanel({
  plan,
  webResearch,
  open = false,
  onToggle,
  className,
  compact = false,
  testId = 'interview-plan-toggle',
}: InterviewPlanPanelProps) {
  if (!plan) return null

  const focusAreas = asArray(plan.focus_areas)
  const suggestedQuestions = asArray(plan.suggested_questions)
  const techStack = asArray(plan.tech_stack)
  const tips = asArray(plan.tips)
  const sources = collectSources(webResearch)
  const difficulty = plan.interview_difficulty ? difficultyLabel[plan.interview_difficulty] ?? plan.interview_difficulty : null

  return (
    <section
      className={cn(
        'rounded-md border border-brand-200/70 dark:border-brand-500/25 bg-surface dark:bg-dark-surface overflow-hidden',
        className,
      )}
    >
      <button
        type="button"
        data-testid={testId}
        onClick={onToggle}
        aria-expanded={open}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-brand-50/50 dark:hover:bg-brand-500/10 transition-colors"
      >
        <span className="flex items-center gap-2 min-w-0">
          <Target className="h-4 w-4 text-brand-600 dark:text-brand-300 flex-shrink-0" />
          <span className="min-w-0">
            <span className="block text-sm font-semibold text-ink-1">面试计划</span>
            <span className="block text-2xs text-ink-3 truncate">
              {plan.target_company || '目标公司'} · {plan.target_position || '目标岗位'}
              {difficulty ? ` · ${difficulty}` : ''}
            </span>
          </span>
        </span>
        {onToggle ? (
          open ? <ChevronUp className="h-4 w-4 text-ink-3 flex-shrink-0" /> : <ChevronDown className="h-4 w-4 text-ink-3 flex-shrink-0" />
        ) : null}
      </button>

      {open && (
        <div className={cn('border-t border-surface-border dark:border-dark-surface-border px-4 py-3', compact ? 'space-y-3' : 'space-y-4')}>
          {focusAreas.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-ink-1 mb-2">
                <ListChecks className="h-3.5 w-3.5 text-brand-500" />
                考察重点
              </div>
              <div className="space-y-2">
                {focusAreas.map((area, index) => (
                  <div key={`${area.area}-${index}`} className="rounded-md bg-surface-muted dark:bg-dark-surface-muted px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-xs font-medium text-ink-1 truncate">{area.area}</div>
                      {typeof area.weight === 'number' && (
                        <div className="text-2xs text-ink-3 tabular-nums">{Math.round(area.weight * 100)}%</div>
                      )}
                    </div>
                    {area.reason && <div className="text-2xs text-ink-3 leading-relaxed mt-1">{area.reason}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {techStack.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {techStack.map((item) => (
                <span key={item} className="rounded bg-brand-50 dark:bg-brand-500/10 px-2 py-1 text-2xs text-brand-700 dark:text-brand-300">
                  {item}
                </span>
              ))}
            </div>
          )}

          {suggestedQuestions.length > 0 && (
            <div>
              <div className="text-xs font-medium text-ink-1 mb-2">问题方向</div>
              <ol className="space-y-1.5">
                {suggestedQuestions.slice(0, compact ? 3 : 5).map((question, index) => (
                  <li key={`${question}-${index}`} className="flex gap-2 text-2xs text-ink-2 leading-relaxed">
                    <span className="text-ink-3 tabular-nums">{index + 1}.</span>
                    <span>{question}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {plan.web_research_summary && (
            <div className="rounded-md bg-surface-muted dark:bg-dark-surface-muted px-3 py-2">
              <div className="flex items-center gap-1.5 text-xs font-medium text-ink-1 mb-1.5">
                <Search className="h-3.5 w-3.5 text-ink-3" />
                信息来源
              </div>
              <div className="text-2xs text-ink-2 leading-relaxed">{plan.web_research_summary}</div>
            </div>
          )}

          {sources.length > 0 && (
            <div className="space-y-1.5">
              {sources.slice(0, compact ? 2 : 4).map((source, index) => (
                <a
                  key={`${source.url || source.title}-${index}`}
                  href={source.url || '#'}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 text-2xs text-brand-600 dark:text-brand-300 hover:underline min-w-0"
                >
                  <ExternalLink className="h-3 w-3 flex-shrink-0" />
                  <span className="truncate">{source.title || source.url || source.content}</span>
                </a>
              ))}
            </div>
          )}

          {tips.length > 0 && (
            <div>
              <div className="text-xs font-medium text-ink-1 mb-2">面试提示</div>
              <ul className="space-y-1">
                {tips.slice(0, compact ? 2 : 4).map((tip, index) => (
                  <li key={`${tip}-${index}`} className="text-2xs text-ink-2 leading-relaxed">
                    {tip}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
