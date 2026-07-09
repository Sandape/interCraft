/**
 * [REQ-048 US3 T072] Full Interview config — max_questions selector.
 *
 * Two radio buttons for the user to pick 10 (中等) or 15 (深入) 题.
 * The chosen value is written to the Zustand store via
 * ``useInterviewModeStore.setMaxQuestions`` so the API call to
 * ``/interview-sessions`` carries the right ``max_questions`` field.
 *
 * The selector renders as a labelled group so screen readers can
 * navigate it as a radio group (data-testid hooks for E2E).
 */
import { useInterviewModeStore } from '@/stores/useInterviewModeStore'

interface FullInterviewConfigProps {
  className?: string
}

const OPTIONS: Array<{
  value: 10 | 15
  label: string
  description: string
}> = [
  {
    value: 10,
    label: '中等（10 题）',
    description: '约 25 分钟，平衡覆盖 5 个维度',
  },
  {
    value: 15,
    label: '深入（15 题）',
    description: '约 40 分钟，深入考察核心维度',
  },
]

export function FullInterviewConfig({ className }: FullInterviewConfigProps) {
  const maxQuestions = useInterviewModeStore((s) => s.maxQuestions)
  const setMaxQuestions = useInterviewModeStore((s) => s.setMaxQuestions)

  return (
    <fieldset
      className={className}
      data-testid="full-interview-config"
      aria-label="完整面试题数选择"
    >
      <legend className="mb-2 text-sm font-medium text-ink-2">选择面试题数</legend>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {OPTIONS.map((opt) => {
          const checked = maxQuestions === opt.value
          return (
            <label
              key={opt.value}
              className={
                'flex cursor-pointer flex-col gap-0.5 rounded-md border px-3 py-2 text-sm transition ' +
                (checked
                  ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/10'
                  : 'border-line-2 bg-bg-1 hover:border-line-1 hover:bg-bg-2')
              }
              data-testid={`full-interview-config-option-${opt.value}`}
            >
              <div className="flex items-center gap-2">
                <input
                  type="radio"
                  name="max_questions"
                  value={opt.value}
                  checked={checked}
                  onChange={() => setMaxQuestions(opt.value)}
                  data-testid={`full-interview-config-radio-${opt.value}`}
                  className="h-3.5 w-3.5 accent-brand-500"
                />
                <span className="font-medium text-ink-1">{opt.label}</span>
              </div>
              <span className="pl-5 text-2xs text-ink-3">{opt.description}</span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}

export default FullInterviewConfig