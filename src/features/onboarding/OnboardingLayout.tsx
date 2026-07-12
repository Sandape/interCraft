import { Check, Layers3 } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { OnboardingStep } from './onboarding-state'
import { cn } from '@/lib/utils'

const stepLabels = ['选择求职目标', '创建根简历草稿', '添加目标岗位', '生成岗位定制简历'] as const

export function OnboardingLayout({
  currentStep,
  activated,
  onSkip,
  children,
}: {
  currentStep: OnboardingStep
  activated: boolean
  onSkip: () => void
  children: React.ReactNode
}) {
  return (
    <div className="onboarding-page min-h-dvh bg-surface-subtle text-ink-1">
      <aside className="onboarding-aside bg-brand-900 text-white">
        <Link to="/" className="inline-flex min-h-11 items-center gap-2.5 text-sm font-semibold" aria-label="InterCraft 首页">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-white text-brand-900">
            <Layers3 className="h-4 w-4" strokeWidth={1.8} />
          </span>
          <span className="hidden lg:inline">InterCraft</span>
        </Link>
        <div className="mt-14 hidden lg:block">
          <p className="text-2xs font-medium uppercase tracking-[0.16em] text-white/45">First activation</p>
          <h1 className="mt-4 text-2xl font-semibold leading-tight tracking-[-0.02em]">
            先做出一份面向具体岗位的简历
          </h1>
          <p className="mt-4 text-sm leading-6 text-white/65">
            只收集完成第一份岗位定制简历所需的信息。之后仍可以继续编辑。
          </p>
        </div>
        <ol className="onboarding-step-list mt-10" aria-label="初始化引导进度">
          {stepLabels.map((label, index) => {
            const step = (index + 1) as OnboardingStep
            const done = activated || currentStep > step
            const active = !activated && currentStep === step
            return (
              <li key={label} className={cn('onboarding-step-item', active && 'is-active', done && 'is-done')}>
                <span className="onboarding-step-number">
                  {done ? <Check className="h-3.5 w-3.5" /> : `0${step}`}
                </span>
                <span className="hidden lg:block">
                  <span className="block text-xs font-medium">{label}</span>
                  <span className="mt-0.5 block text-2xs text-white/45">步骤 {step} / 4</span>
                </span>
              </li>
            )
          })}
        </ol>
        <p className="mt-auto hidden text-2xs leading-5 text-white/45 lg:block">
          引导进度会自动保存在当前浏览器中。Activation 完成后不再重复打扰。
        </p>
      </aside>

      <main className="onboarding-main min-w-0">
        <header className="flex min-h-16 items-center justify-between border-b border-surface-border bg-surface px-5 sm:px-8">
          <div className="text-xs text-ink-3">
            {activated ? '初始化完成' : `步骤 ${currentStep} / 4 · 自动保存`}
          </div>
          {!activated && (
            <button type="button" onClick={onSkip} className="btn-ghost btn-lg min-h-11">
              暂时跳过
            </button>
          )}
        </header>
        <div className="onboarding-content mx-auto w-full max-w-4xl px-5 py-8 sm:px-8 sm:py-12 lg:px-12 lg:py-16">
          {children}
        </div>
      </main>
    </div>
  )
}
