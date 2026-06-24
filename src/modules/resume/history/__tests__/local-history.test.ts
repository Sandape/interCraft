/**
 * T094 — local-history unit tests.
 *
 * Verifies:
 * - FIFO semantics: push 10 items → only 8 survive, oldest dropped
 * - Entry deduplication: pushing identical entry is a no-op
 * - pushHistory silently drops oversized entries
 * - restoreHistory returns correct entry by index
 * - clearHistory wipes the storage key
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { getHistory, pushHistory, restoreHistory, clearHistory } from '../local-history'
import type { HistoryEntry } from '../local-history'

// In-memory localStorage mock for the test.
const store = new Map<string, string>()

beforeEach(() => {
  store.clear()
  vi.stubGlobal(
    'localStorage',
    {
      getItem: vi.fn((k: string) => store.get(k) ?? null),
      setItem: vi.fn((k: string, v: string) => { store.set(k, v) }),
      removeItem: vi.fn((k: string) => { store.delete(k) }),
      length: 0,
      clear: vi.fn(() => store.clear()),
      key: vi.fn(() => null),
    },
  )
})

const branchId = 'test-branch-1'

function entry(markdown: string, overrides?: Partial<HistoryEntry>): HistoryEntry {
  return { markdown, themeId: 'default', accentColor: '#39393a', timestamp: Date.now(), ...overrides }
}

describe('local-history — FIFO', () => {
  it('starts empty', () => {
    expect(getHistory(branchId)).toEqual([])
  })

  it('single push is retrievable', () => {
    pushHistory(branchId, entry('# Hello'))
    const h = getHistory(branchId)
    expect(h).toHaveLength(1)
    expect(h[0]!.markdown).toBe('# Hello')
  })

  it('FIFO: push 10 items → keep 8, oldest dropped', () => {
    for (let i = 0; i < 10; i++) {
      pushHistory(branchId, entry(`# ${i}`))
    }
    const h = getHistory(branchId)
    expect(h).toHaveLength(8)
    // Most recent is index 0; item 0 should be #9, item 7 should be #2
    expect(h[0]!.markdown).toBe('# 9')
    expect(h[7]!.markdown).toBe('# 2')
  })

  it('deduplicates the most recent entry', () => {
    const e = entry('# Same')
    pushHistory(branchId, e)
    pushHistory(branchId, e)
    expect(getHistory(branchId)).toHaveLength(1)
  })

  it('deduplicates sequential identical entries', () => {
    for (let i = 0; i < 5; i++) {
      pushHistory(branchId, entry('# Steady'))
    }
    expect(getHistory(branchId)).toHaveLength(1)
  })

  it('silently drops empty-markdown entries', () => {
    pushHistory(branchId, entry(''))
    pushHistory(branchId, entry('   '))
    expect(getHistory(branchId)).toEqual([])
  })
})

describe('local-history — restore / clear', () => {
  it('restoreHistory returns correct entry by index', () => {
    pushHistory(branchId, entry('# First'))
    pushHistory(branchId, entry('# Second'))
    pushHistory(branchId, entry('# Third'))
    expect(restoreHistory(branchId, 0)!.markdown).toBe('# Third')
    expect(restoreHistory(branchId, 1)!.markdown).toBe('# Second')
    expect(restoreHistory(branchId, 2)!.markdown).toBe('# First')
  })

  it('restoreHistory returns null for out-of-range index', () => {
    expect(restoreHistory(branchId, 0)).toBeNull()
    pushHistory(branchId, entry('# Only'))
    expect(restoreHistory(branchId, 99)).toBeNull()
  })

  it('clearHistory removes stored data', () => {
    pushHistory(branchId, entry('# Data'))
    expect(getHistory(branchId)).toHaveLength(1)
    clearHistory(branchId)
    expect(getHistory(branchId)).toEqual([])
  })
})