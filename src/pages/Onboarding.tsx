import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { OnboardingLayout } from '@/features/onboarding/OnboardingLayout'
import {
  BaselineStep,
  GenerateStep,
  GoalStep,
  TargetStep,
} from '@/features/onboarding/OnboardingSteps'
import { OnboardingSuccess } from '@/features/onboarding/OnboardingSuccess'
import {
  loadOnboardingState,
  markOnboardingActivated,
  markOnboardingSkipped,
  onboardingStorageKey,
  resumeOnboarding,
  saveOnboardingState,
  type OnboardingState,
  type OnboardingStep,
} from '@/features/onboarding/onboarding-state'
import { publicDemoData } from '@/data/publicDemoData'
import { trackProductEvent } from '@/lib/product-events'
import { useAuthStore } from '@/stores/useAuthStore'
import '@/styles/public-product.css'

type GenerationState = 'idle' | 'loading'

export default function Onboarding() {
  const navigate = useNavigate()
  const userId = useAuthStore((current) => current.user?.id)
  const storageKey = onboardingStorageKey(userId)
  const [searchParams] = useSearchParams()
  const requestedResume = searchParams.get('resume') === '1'
  const resumedRef = useRef(false)
  const generationTimerRef = useRef<number | null>(null)
  const [state, setState] = useState<OnboardingState>(() => {
    const loaded = loadOnboardingState(undefined, storageKey)
    if (requestedResume && loaded.status !== 'activated') {
      resumedRef.current = true
      return resumeOnboarding(loaded)
    }
    return loaded
  })
  const [error, setError] = useState<string | null>(null)
  const [generationState, setGenerationState] = useState<GenerationState>('idle')

  useEffect(() => saveOnboardingState(state, undefined, storageKey), [state, storageKey])

  useEffect(() => {
    if (resumedRef.current) {
      trackProductEvent({ name: 'onboarding_resumed', source: 'dashboard_recovery', step: state.currentStep })
    }
  }, [])

  useEffect(() => () => {
    if (generationTimerRef.current !== null) window.clearTimeout(generationTimerRef.current)
  }, [])

  const updateState = (next: OnboardingState) => {
    setError(null)
    setState({ ...next, status: next.status === 'activated' ? 'activated' : 'in_progress', savedAt: new Date().toISOString() })
  }

  const moveTo = (step: OnboardingStep) => {
    setError(null)
    setState((current) => ({ ...current, status: 'in_progress', currentStep: step, savedAt: new Date().toISOString() }))
  }

  const completeStep = (nextStep: OnboardingStep) => {
    trackProductEvent({ name: 'onboarding_step_completed', source: 'onboarding', step: state.currentStep })
    moveTo(nextStep)
  }

  const nextFromGoal = () => {
    if (!state.goal.stage || !state.goal.targetRole.trim()) {
      setError('请选择求职阶段并填写目标方向。')
      return
    }
    completeStep(2)
  }

  const nextFromBaseline = () => {
    if (!state.baseline.entryMode) {
      setError('请选择一种根简历起步方式。')
      return
    }
    if (state.baseline.entryMode !== 'blank' && state.baseline.content.trim().length < 12) {
      setError('请至少写下 12 个字符的真实经历线索，或选择空白草稿。')
      return
    }
    completeStep(3)
  }

  const nextFromTarget = () => {
    if (!state.target.mode) {
      setError('请选择粘贴 JD 或岗位模板。')
      return
    }
    if (state.target.mode === 'jd' && state.target.jd.trim().length < 40) {
      setError('岗位描述过短，请补充到至少 40 个字符。')
      return
    }
    if (state.target.mode === 'template' && !state.target.templateId) {
      setError('请选择一个岗位起步模板。')
      return
    }
    completeStep(4)
  }

  const generateDemo = () => {
    if (generationState === 'loading') return
    setError(null)
    setGenerationState('loading')
    generationTimerRef.current = window.setTimeout(() => {
      const analysis = {
        matchScore: publicDemoData.derivedResume.matchScore,
        strengths: [...publicDemoData.derivedResume.strengths],
        gaps: [...publicDemoData.derivedResume.gaps],
        suggestions: [...publicDemoData.derivedResume.suggestions],
      }
      const activated = markOnboardingActivated({ ...state, analysis })
      setState(activated)
      saveOnboardingState(activated, undefined, storageKey)
      setGenerationState('idle')
      trackProductEvent({ name: 'onboarding_activated', source: 'onboarding', step: 4 })
    }, 850)
  }

  const skip = () => {
    const skipped = markOnboardingSkipped(state)
    setState(skipped)
    saveOnboardingState(skipped, undefined, storageKey)
    trackProductEvent({ name: 'onboarding_skipped', source: 'onboarding', step: state.currentStep })
    navigate('/dashboard', { replace: true })
  }

  const activated = state.status === 'activated' && Boolean(state.analysis)

  return (
    <OnboardingLayout currentStep={state.currentStep} activated={activated} onSkip={skip}>
      {resumedRef.current && !activated && (
        <div className="mb-6 border border-brand-200 bg-brand-50 px-4 py-3 text-xs text-brand-700" role="status">
          已恢复上次进度，你可以从步骤 {state.currentStep} 继续。
        </div>
      )}
      {activated ? (
        <OnboardingSuccess state={state} />
      ) : state.currentStep === 1 ? (
        <GoalStep state={state} error={error} onChange={updateState} onNext={nextFromGoal} />
      ) : state.currentStep === 2 ? (
        <BaselineStep state={state} error={error} onChange={updateState} onBack={() => moveTo(1)} onNext={nextFromBaseline} />
      ) : state.currentStep === 3 ? (
        <TargetStep state={state} error={error} onChange={updateState} onBack={() => moveTo(2)} onNext={nextFromTarget} />
      ) : (
        <GenerateStep state={state} error={error} loading={generationState === 'loading'} onBack={() => moveTo(3)} onGenerate={generateDemo} />
      )}
    </OnboardingLayout>
  )
}
