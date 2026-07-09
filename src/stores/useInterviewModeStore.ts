/**
 * useInterviewModeStore — REQ-048 US1 mode-selection Zustand store.
 *
 * Tracks the user's pick on the 「面试方式」 selection page so that
 * (a) the start-interview API call carries the mode, and
 * (b) navigating back to 「岗位参数」 then forward again clears the
 *     previous pick (FR-005 / AC-03).
 *
 * No persistence (Edge-8 / AC-03b): F5 / page.reload drops the state and
 * the InterviewModeSelect page is responsible for routing back to
 * /interviews/new.
 */
import { create } from 'zustand'

export type InterviewMode = 'quick_drill' | 'full' | 'doubao'
export type SubMode = 'quick_drill' | 'full'

export interface InterviewModeState {
  /** Top-level mode ('quick_drill' / 'full' / 'doubao'). null = unselected. */
  mode: InterviewMode | null
  /** User-selected question-count for 'full' mode (10 or 15). */
  maxQuestions: 10 | 15 | null
  /** Toggle for variant re-take (US5). Default false per AC-25. */
  useVariants: boolean
  /** Sub-mode is recorded separately so 「返回上一步」 can re-select. */
  subMode: SubMode | null

  setMode: (mode: InterviewMode) => void
  setSubMode: (subMode: SubMode) => void
  setMaxQuestions: (n: 10 | 15) => void
  setUseVariants: (v: boolean) => void
  reset: () => void
}

const INITIAL: Pick<InterviewModeState, 'mode' | 'maxQuestions' | 'useVariants' | 'subMode'> = {
  mode: null,
  maxQuestions: null,
  useVariants: false,
  subMode: null,
}

export const useInterviewModeStore = create<InterviewModeState>((set) => ({
  ...INITIAL,
  setMode: (mode) => set({ mode, subMode: null }),
  setSubMode: (subMode) => set({ subMode }),
  setMaxQuestions: (maxQuestions) => set({ maxQuestions }),
  setUseVariants: (useVariants) => set({ useVariants }),
  reset: () => set({ ...INITIAL }),
}))

/** Test-only re-export — keeps AC-03 unit test deterministic. */
export const __resetInterviewModeStoreForTests = (): void => {
  useInterviewModeStore.setState({ ...INITIAL })
}

export default useInterviewModeStore