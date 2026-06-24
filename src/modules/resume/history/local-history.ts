/**
 * Local edit history (spec 027 US7 FR-051-053).
 *
 * Writes a FIFO 8-entry trail to `localStorage` keyed by branch id.
 * Each entry contains the full snapshot (markdown, theme_id, accent_color,
 * timestamp) so `restoreHistory` can reload it byte-for-byte.
 *
 * Size cap: ~100 KB per entry (JSON.stringify overhead). Entries
 * exceeding the cap are silently dropped rather than truncated.
 */

const MAX_ENTRIES = 8
const MAX_BYTES = 102400 // 100 KB per entry

export interface HistoryEntry {
  markdown: string
  themeId: string
  accentColor: string
  timestamp: number
}

function storageKey(branchId: string): string {
  return `rs-history-${branchId}`
}

/** Estimate byte length of a JSON-serialised entry. */
function entryBytes(e: HistoryEntry): number {
  const json = JSON.stringify(e)
  // In V8 each char is 1 byte in JSON strings (ASCII-ish markdown).
  return new TextEncoder().encode(json).length
}

/** Read the current history for a branch (may be empty). */
export function getHistory(branchId: string): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(storageKey(branchId))
    if (!raw) return []
    const parsed = JSON.parse(raw) as HistoryEntry[]
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (e) =>
        typeof e.markdown === 'string' &&
        typeof e.themeId === 'string' &&
        typeof e.accentColor === 'string' &&
        typeof e.timestamp === 'number',
    )
  } catch {
    return []
  }
}

/**
 * Push a new history entry (FR-051).
 *
 * - Appends at index 0, drops the oldest when exceeding MAX_ENTRIES (FIFO).
 * - Drops entries exceeding MAX_BYTES (silently, no error thrown).
 * - No-op when `markdown` is empty or only whitespace.
 */
export function pushHistory(branchId: string, entry: HistoryEntry): void {
  if (!entry.markdown?.trim()) return
  // Enforce per-entry byte cap.
  if (entryBytes(entry) > MAX_BYTES) return

  const history = getHistory(branchId)
  // Dedupe against the most recent identical entry (silent no-op).
  if (history.length > 0 && areEntriesEqual(history[0]!, entry)) return

  history.unshift(entry)
  // FIFO: keep at most MAX_ENTRIES.
  if (history.length > MAX_ENTRIES) {
    history.splice(MAX_ENTRIES)
  }
  try {
    localStorage.setItem(storageKey(branchId), JSON.stringify(history))
  } catch {
    // localStorage full — silently drop.
  }
}

function areEntriesEqual(a: HistoryEntry, b: HistoryEntry): boolean {
  return a.markdown === b.markdown && a.themeId === b.themeId && a.accentColor === b.accentColor
}

/**
 * Restore history entry at `index` (0 = most recent).
 * Returns the entry or null when the index is out of range.
 *
 * The caller sets markdown/theme/accent from the payload and navigates if
 * needed (FR-053: content, theme, and colour all restored at once).
 */
export function restoreHistory(branchId: string, index: number): HistoryEntry | null {
  const history = getHistory(branchId)
  return history[index] ?? null
}

/**
 * Clear all history for a branch (e.g. when the branch is deleted).
 */
export function clearHistory(branchId: string): void {
  try {
    localStorage.removeItem(storageKey(branchId))
  } catch {
    // ignore
  }
}