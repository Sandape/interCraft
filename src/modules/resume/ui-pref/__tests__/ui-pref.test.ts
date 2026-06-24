/**
 * T095 — UI pref persistence tests.
 *
 * Verifies:
 * - savePref / loadPref round-trip
 * - Partial merge: saving only mode preserves existing splitRatio
 * - Per-branch isolation: different branch IDs have independent storage
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { loadPref, savePref } from '../index'

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

describe('ui-pref', () => {
  it('returns empty object when nothing is stored', () => {
    expect(loadPref('branch-1')).toEqual({})
  })

  it('savePref round-trips mode and splitRatio', () => {
    savePref('branch-1', { mode: 'code', splitRatio: 65 })
    const loaded = loadPref('branch-1')
    expect(loaded.mode).toBe('code')
    expect(loaded.splitRatio).toBe(65)
  })

  it('savePref partial merge preserves existing values', () => {
    savePref('branch-1', { splitRatio: 50 })
    savePref('branch-1', { mode: 'quick' })
    const loaded = loadPref('branch-1')
    expect(loaded.splitRatio).toBe(50)
    expect(loaded.mode).toBe('quick')
  })

  it('per-branch isolation: two branches store independently', () => {
    savePref('branch-a', { mode: 'code', splitRatio: 60 })
    savePref('branch-b', { mode: 'quick', splitRatio: 40 })
    const a = loadPref('branch-a')
    const b = loadPref('branch-b')
    expect(a.mode).toBe('code')
    expect(b.mode).toBe('quick')
    expect(a.splitRatio).toBe(60)
    expect(b.splitRatio).toBe(40)
  })

  it('ignores invalid stored JSON gracefully', () => {
    store.set('rs-ui-pref-bad', 'not-json')
    expect(loadPref('bad')).toEqual({})
  })
})