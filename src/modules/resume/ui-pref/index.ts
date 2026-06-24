/**
 * UI preference persistence (spec 027 US7 FR-054-056).
 *
 * Stores editor mode, split ratio, and scroll position per branch in
 * `localStorage` under `rs-ui-pref-{branchId}`. Values survive page reloads
 * and re-openings of the same branch.
 */

const PREFIX = 'rs-ui-pref-'

export interface UIPreferences {
  /** 'quick' | 'code' — saved on mode toggle (FR-054). */
  mode?: 'quick' | 'code'
  /** Percentage (20–80) — saved on drag end (FR-055). */
  splitRatio?: number
  /** ScrollTop of the preview container — saved on scroll debounced (FR-056). */
  scrollPos?: number
  /** Cursor in the markdown code editor (session-only but stored for convenience). */
  cursorPos?: number
}

function storageKey(branchId: string): string {
  return `${PREFIX}${branchId}`
}

/** Read UI preferences for a branch. Returns default values when nothing is stored. */
export function loadPref(branchId: string): UIPreferences {
  try {
    const raw = localStorage.getItem(storageKey(branchId))
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return {}
    return {
      mode: parsed.mode === 'quick' || parsed.mode === 'code' ? parsed.mode : undefined,
      splitRatio: typeof parsed.splitRatio === 'number' ? parsed.splitRatio : undefined,
      scrollPos: typeof parsed.scrollPos === 'number' ? parsed.scrollPos : undefined,
      cursorPos: typeof parsed.cursorPos === 'number' ? parsed.cursorPos : undefined,
    }
  } catch {
    return {}
  }
}

/** Save UI preferences for a branch (merges partial input with current values). */
export function savePref(branchId: string, partial: Partial<UIPreferences>): void {
  const current = loadPref(branchId)
  const merged = { ...current, ...partial }
  try {
    localStorage.setItem(storageKey(branchId), JSON.stringify(merged))
  } catch {
    // localStorage full — silently drop
  }
}