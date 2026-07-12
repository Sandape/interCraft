export const ONBOARDING_STORAGE_KEY = 'intercraft:onboarding:v1'
const MAX_STORED_STATE_LENGTH = 100_000

export function onboardingStorageKey(userId?: string | null): string {
  return userId ? `${ONBOARDING_STORAGE_KEY}:${userId}` : ONBOARDING_STORAGE_KEY
}

export type OnboardingStatus = 'in_progress' | 'skipped' | 'activated'
export type OnboardingStep = 1 | 2 | 3 | 4
export type JobSearchStage =
  | ''
  | 'campus'
  | 'experienced'
  | 'internship'
  | 'career_switch'
  | 'exploring'
export type ResumeEntryMode = '' | 'paste' | 'structured' | 'blank'
export type TargetEntryMode = '' | 'jd' | 'template'

export interface OnboardingAnalysis {
  matchScore: number
  strengths: string[]
  gaps: string[]
  suggestions: string[]
}

export interface OnboardingState {
  version: 1
  status: OnboardingStatus
  currentStep: OnboardingStep
  goal: {
    stage: JobSearchStage
    targetRole: string
    city: string
  }
  baseline: {
    entryMode: ResumeEntryMode
    content: string
  }
  target: {
    mode: TargetEntryMode
    jd: string
    templateId: string
  }
  analysis: OnboardingAnalysis | null
  savedAt: string
  activatedAt: string | null
}

export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

function nowIso(): string {
  return new Date().toISOString()
}

export function createOnboardingState(): OnboardingState {
  return {
    version: 1,
    status: 'in_progress',
    currentStep: 1,
    goal: { stage: '', targetRole: '', city: '' },
    baseline: { entryMode: '', content: '' },
    target: { mode: '', jd: '', templateId: '' },
    analysis: null,
    savedAt: nowIso(),
    activatedAt: null,
  }
}

function defaultStorage(): StorageLike | null {
  return typeof window === 'undefined' ? null : window.localStorage
}

export function saveOnboardingState(
  state: OnboardingState,
  storage: StorageLike | null = defaultStorage(),
  storageKey = ONBOARDING_STORAGE_KEY,
): void {
  try {
    storage?.setItem(storageKey, JSON.stringify(state))
  } catch {
    // Storage can be disabled or full. Keep the current session usable even
    // when persistence is unavailable; form validation remains authoritative.
  }
}

export function loadOnboardingState(
  storage: StorageLike | null = defaultStorage(),
  storageKey = ONBOARDING_STORAGE_KEY,
): OnboardingState {
  const raw = storage?.getItem(storageKey)
  if (!raw || raw.length > MAX_STORED_STATE_LENGTH) return createOnboardingState()

  try {
    const parsed: unknown = JSON.parse(raw)
    return isOnboardingState(parsed) ? parsed : createOnboardingState()
  } catch {
    return createOnboardingState()
  }
}

export function hasSavedOnboardingState(
  storage: StorageLike | null = defaultStorage(),
  storageKey = ONBOARDING_STORAGE_KEY,
): boolean {
  try {
    return Boolean(storage?.getItem(storageKey))
  } catch {
    return false
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function isOnboardingState(value: unknown): value is OnboardingState {
  if (!isRecord(value) || !isRecord(value.goal) || !isRecord(value.baseline) || !isRecord(value.target)) {
    return false
  }

  const validStatus = ['in_progress', 'skipped', 'activated'].includes(String(value.status))
  const validStep = [1, 2, 3, 4].includes(Number(value.currentStep))
  const validGoal =
    ['', 'campus', 'experienced', 'internship', 'career_switch', 'exploring'].includes(
      String(value.goal.stage),
    ) &&
    typeof value.goal.targetRole === 'string' &&
    typeof value.goal.city === 'string'
  const validBaseline =
    ['', 'paste', 'structured', 'blank'].includes(String(value.baseline.entryMode)) &&
    typeof value.baseline.content === 'string'
  const validTarget =
    ['', 'jd', 'template'].includes(String(value.target.mode)) &&
    typeof value.target.jd === 'string' &&
    typeof value.target.templateId === 'string'
  const validAnalysis =
    value.analysis === null ||
    (isRecord(value.analysis) &&
      typeof value.analysis.matchScore === 'number' &&
      Number.isFinite(value.analysis.matchScore) &&
      value.analysis.matchScore >= 0 &&
      value.analysis.matchScore <= 100 &&
      isStringArray(value.analysis.strengths) &&
      isStringArray(value.analysis.gaps) &&
      isStringArray(value.analysis.suggestions))

  return (
    value.version === 1 &&
    validStatus &&
    validStep &&
    validGoal &&
    validBaseline &&
    validTarget &&
    validAnalysis &&
    typeof value.savedAt === 'string' &&
    (value.activatedAt === null || typeof value.activatedAt === 'string')
  )
}

export function markOnboardingSkipped(state: OnboardingState): OnboardingState {
  return { ...state, status: 'skipped', savedAt: nowIso() }
}

export function resumeOnboarding(state: OnboardingState): OnboardingState {
  return state.status === 'activated'
    ? state
    : { ...state, status: 'in_progress', savedAt: nowIso() }
}

export function markOnboardingActivated(state: OnboardingState): OnboardingState {
  const timestamp = nowIso()
  return {
    ...state,
    status: 'activated',
    currentStep: 4,
    savedAt: timestamp,
    activatedAt: timestamp,
  }
}

export function shouldShowOnboardingRecovery(state: OnboardingState): boolean {
  return state.status !== 'activated'
}

export function clearOnboardingState(
  storage: StorageLike | null = defaultStorage(),
  storageKey = ONBOARDING_STORAGE_KEY,
): void {
  storage?.removeItem(storageKey)
}
