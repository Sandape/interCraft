import { describe, expect, it } from 'vitest'
import {
  createOnboardingState,
  hasSavedOnboardingState,
  loadOnboardingState,
  markOnboardingActivated,
  markOnboardingSkipped,
  onboardingStorageKey,
  saveOnboardingState,
  shouldShowOnboardingRecovery,
  type StorageLike,
} from '../onboarding-state'

function memoryStorage(): StorageLike {
  const values = new Map<string, string>()
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  }
}

describe('onboarding state', () => {
  it('starts at the job-goal step with an incomplete status', () => {
    const state = createOnboardingState()

    expect(state.status).toBe('in_progress')
    expect(state.currentStep).toBe(1)
    expect(state.goal.stage).toBe('')
    expect(state.activatedAt).toBeNull()
  })

  it('round-trips a saved draft so refresh can resume it', () => {
    const storage = memoryStorage()
    const state = {
      ...createOnboardingState(),
      currentStep: 3 as const,
      goal: { stage: 'career_switch' as const, targetRole: '产品经理', city: '上海' },
      baseline: { entryMode: 'paste' as const, content: '五年用户研究与增长经验' },
    }

    saveOnboardingState(state, storage)

    expect(loadOnboardingState(storage)).toEqual(state)
  })

  it('recovers safely from malformed local data', () => {
    const storage = memoryStorage()
    storage.setItem('intercraft:onboarding:v1', '{broken')

    const state = loadOnboardingState(storage)

    expect(state.status).toBe('in_progress')
    expect(state.currentStep).toBe(1)
  })

  it('rejects a structurally invalid activated result instead of crashing the result view', () => {
    const storage = memoryStorage()
    storage.setItem(
      'intercraft:onboarding:v1',
      JSON.stringify({
        ...createOnboardingState(),
        status: 'activated',
        analysis: { matchScore: 82, strengths: null, gaps: [], suggestions: [] },
      }),
    )

    const state = loadOnboardingState(storage)

    expect(state.status).toBe('in_progress')
    expect(state.analysis).toBeNull()
  })

  it('isolates drafts by authenticated account', () => {
    const storage = memoryStorage()
    const accountAKey = onboardingStorageKey('account-a')
    const accountBKey = onboardingStorageKey('account-b')
    const accountAState = {
      ...createOnboardingState(),
      goal: { stage: 'campus' as const, targetRole: '产品经理', city: '' },
    }

    saveOnboardingState(accountAState, storage, accountAKey)

    expect(loadOnboardingState(storage, accountAKey).goal.targetRole).toBe('产品经理')
    expect(loadOnboardingState(storage, accountBKey).goal.targetRole).toBe('')
    expect(hasSavedOnboardingState(storage, accountAKey)).toBe(true)
    expect(hasSavedOnboardingState(storage, accountBKey)).toBe(false)
  })

  it('keeps skipped progress recoverable until activation', () => {
    const skipped = markOnboardingSkipped({
      ...createOnboardingState(),
      currentStep: 2,
    })

    expect(skipped.status).toBe('skipped')
    expect(skipped.currentStep).toBe(2)
    expect(shouldShowOnboardingRecovery(skipped)).toBe(true)

    const activated = markOnboardingActivated(skipped)
    expect(activated.status).toBe('activated')
    expect(activated.activatedAt).not.toBeNull()
    expect(shouldShowOnboardingRecovery(activated)).toBe(false)
  })
})
