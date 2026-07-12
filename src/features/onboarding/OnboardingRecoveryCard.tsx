import { ArrowRight, Route } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  loadOnboardingState,
  onboardingStorageKey,
  shouldShowOnboardingRecovery,
} from './onboarding-state'
import { useAuthStore } from '@/stores/useAuthStore'

export function OnboardingRecoveryCard() {
  const userId = useAuthStore((current) => current.user?.id)
  const storageKey = onboardingStorageKey(userId)
  if (typeof window === 'undefined' || !window.localStorage.getItem(storageKey)) {
    return null
  }
  const state = loadOnboardingState(undefined, storageKey)
  if (!shouldShowOnboardingRecovery(state)) return null

  return (
    <section
      className="mb-6 flex flex-col gap-4 border border-brand-200 bg-brand-50 px-4 py-4 sm:flex-row sm:items-center sm:justify-between"
      data-testid="onboarding-recovery"
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-md bg-surface text-brand-600 shadow-notion-sm">
          <Route className="h-4 w-4" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-ink-1">继续创建第一份岗位定制简历</h2>
          <p className="mt-1 text-xs leading-5 text-ink-3">
            已保存到步骤 {state.currentStep} / 4。完成后将看到匹配分析、能力差距和优化建议。
          </p>
        </div>
      </div>
      <Link to="/onboarding?resume=1" className="btn-primary btn-md min-h-10 flex-none">
        继续引导 <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </section>
  )
}
