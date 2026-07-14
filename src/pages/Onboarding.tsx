import { useCallback, useEffect, useRef, useState } from 'react'
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
import { createRootResume, getRootResume } from '@/modules/resume/derive/api'
import { ApiError } from '@/api/errors'
import { defaultResumeDataV2 } from '@/modules/resume/v2/schema/defaults'
import type { ResumeDataV2 } from '@/modules/resume/v2/schema/data'
import '@/styles/public-product.css'

type GenerationState = 'idle' | 'loading'
type RootPersistState =
  | { kind: 'idle' }
  | { kind: 'pending'; startedAt: string }
  | { kind: 'created'; rootId: string; markerLength: number; existing: boolean }
  | { kind: 'failed'; message: string; retryable: boolean }

function buildBlankRootPayload(): ResumeDataV2 {
  // Blank onboarding: complete v2 document with metadata.markdown.sourceMarkdown
  // exactly empty and no demo identity / facts. We deep-merge with the schema
  // defaults so the backend validates the payload, but every user-visible
  // field (basics, summary, marker) is blank.
  const defaults = defaultResumeDataV2
  return {
    ...defaults,
    picture: { ...defaults.picture },
    basics: {
      ...defaults.basics,
      name: '',
      headline: '',
      email: '',
      phone: '',
      location: '',
      website: { url: '', label: '' },
      customFields: [],
    },
    summary: { ...defaults.summary, content: '' },
    sections: Object.fromEntries(
      Object.entries(defaults.sections).map(([key, section]) => [
        key,
        { ...section, items: [] },
      ]),
    ) as ResumeDataV2['sections'],
    customSections: [],
    metadata: {
      ...defaults.metadata,
      markdown: {
        ...defaults.metadata.markdown,
        sourceMarkdown: '',
      },
    },
  }
}

function buildMarkerRootPayload(marker: string): ResumeDataV2 {
  // Paste / structured mode: preserve the user's exact marker byte-for-byte.
  // We still send a complete v2 document so the backend can validate the
  // full schema; only the sourceMarkdown field differs from blank mode.
  const blank = buildBlankRootPayload()
  return {
    ...blank,
    metadata: {
      ...blank.metadata,
      markdown: {
        ...blank.metadata.markdown,
        sourceMarkdown: marker,
      },
    },
  }
}

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
  const [rootPersist, setRootPersist] = useState<RootPersistState>({ kind: 'idle' })
  // Single-flight guard: useRef boolean so two rapid calls within the
  // same render cycle both see the guard as locked — React state alone
  // would let the second call through before the re-render.
  const persistInFlightRef = useRef(false)
  const persistInFlight = rootPersist.kind === 'pending'

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
    if (persistInFlight) return
    setError(null)
    setState((current) => ({ ...current, status: 'in_progress', currentStep: step, savedAt: new Date().toISOString() }))
  }

  const completeStep = (nextStep: OnboardingStep) => {
    if (persistInFlight) return
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

  const persistRootResume = useCallback(async (): Promise<{ ok: true; rootId: string; existing: boolean } | { ok: false; message: string; retryable: boolean }> => {
    if (!userId) {
      return { ok: false, message: '请先登录后再创建根简历。', retryable: false }
    }
    // Synchronous ref guard — faster than React state for same-render clicks.
    if (persistInFlightRef.current) {
      return { ok: false, message: '正在保存根简历，请稍后。', retryable: true }
    }
    persistInFlightRef.current = true
    setRootPersist({ kind: 'pending', startedAt: new Date().toISOString() })
    const marker =
      state.baseline.entryMode === 'blank'
        ? ''
        : state.baseline.content
    const payload =
      state.baseline.entryMode === 'blank'
        ? buildBlankRootPayload()
        : buildMarkerRootPayload(marker)

    try {
      const created = (await createRootResume({
        name: '根简历',
        slug: 'root-resume',
        data: payload as unknown as Record<string, unknown>,
      })) as { id?: string; data?: { metadata?: { markdown?: { sourceMarkdown?: string } } } }
      const rootId = created?.id ?? ''
      setRootPersist({ kind: 'created', rootId, markerLength: -1, existing: false })
      return { ok: true, rootId, existing: false }
    } catch (err) {
      // 409 ROOT_EXISTS → the user already has a root. Treat as success:
      // resolve the existing row's path and advance.
      if (err instanceof ApiError && err.status === 409 && err.code === 'ROOT_EXISTS') {
        try {
          const existing = (await getRootResume()) as { id?: string }
          const rootId = existing?.id ?? ''
          setRootPersist({ kind: 'created', rootId, markerLength: -1, existing: true })
          return { ok: true, rootId, existing: true }
        } catch (reuseErr) {
          const message =
            reuseErr instanceof Error
              ? reuseErr.message
              : '无法读取已有根简历，请稍后重试。'
          setRootPersist({ kind: 'failed', message, retryable: true })
          return { ok: false, message, retryable: true }
        }
      }
      const message =
        err instanceof Error ? err.message : '创建根简历失败，请稍后重试。'
      const retryable =
        !(err instanceof ApiError) || err.status >= 500 || err.status === 0 || err.status === 429
      setRootPersist({ kind: 'failed', message, retryable })
      return { ok: false, message, retryable }
    } finally {
      persistInFlightRef.current = false
    }
  }, [state.baseline.entryMode, state.baseline.content, userId])

  const nextFromBaseline = async () => {
    if (persistInFlight || persistInFlightRef.current) return
    if (!state.baseline.entryMode) {
      setError('请选择一种根简历起步方式。')
      return
    }
    if (state.baseline.entryMode !== 'blank' && state.baseline.content.trim().length < 12) {
      setError('请至少写下 12 个字符的真实经历线索，或选择空白草稿。')
      return
    }
    const result = await persistRootResume()
    if (!result.ok) {
      setError(result.message)
      return
    }
    completeStep(3)
  }

  const retryBaseline = async () => {
    if (persistInFlight || persistInFlightRef.current) return
    setError(null)
    const result = await persistRootResume()
    if (!result.ok) {
      setError(result.message)
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
    if (persistInFlight) return
    const skipped = markOnboardingSkipped(state)
    setState(skipped)
    saveOnboardingState(skipped, undefined, storageKey)
    trackProductEvent({ name: 'onboarding_skipped', source: 'onboarding', step: state.currentStep })
    navigate('/dashboard', { replace: true })
  }

  const activated = state.status === 'activated' && Boolean(state.analysis)

  return (
    <OnboardingLayout currentStep={state.currentStep} activated={activated} onSkip={skip} skipDisabled={persistInFlight}>
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
        <BaselineStep
          state={state}
          error={error}
          persistPending={persistInFlight}
          persistFailed={rootPersist.kind === 'failed'}
          onChange={updateState}
          onBack={() => moveTo(1)}
          onNext={nextFromBaseline}
          onRetry={retryBaseline}
        />
      ) : state.currentStep === 3 ? (
        <TargetStep state={state} error={error} onChange={updateState} onBack={() => moveTo(2)} onNext={nextFromTarget} />
      ) : (
        <GenerateStep state={state} error={error} loading={generationState === 'loading'} onBack={() => moveTo(3)} onGenerate={generateDemo} />
      )}
    </OnboardingLayout>
  )
}