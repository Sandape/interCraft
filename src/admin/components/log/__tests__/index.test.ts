/**
 * Unit tests — REQ-039 B2.
 *
 * Covers the hash normalization logic (FR-022), the SHA256 prefix via
 * Web Crypto (FR-023), and a few microGantt formatting helpers.
 *
 * jsdom (test environment) does not expose crypto.subtle by default,
 * so we install `fake-indexeddb`-style polyfill via the global
 * `crypto` shim in setup. Where subtle is unavailable the helper
 * returns "00000000" — covered by the "subtle missing" assertion.
 */
import { describe, expect, it } from 'vitest'
import {
  computeErrorHash,
  formatDuration,
  normalizeStatus,
  normalizeType,
} from '../index'

describe('normalizeStatus', () => {
  it('maps backend enums to 4 UI tokens', () => {
    expect(normalizeStatus('success')).toBe('success')
    expect(normalizeStatus('succeeded')).toBe('success')
    expect(normalizeStatus('failed')).toBe('failed')
    expect(normalizeStatus('error')).toBe('failed')
    expect(normalizeStatus('pending')).toBe('pending')
    expect(normalizeStatus('queued')).toBe('pending')
    expect(normalizeStatus('running')).toBe('running')
    expect(normalizeStatus('in_progress')).toBe('running')
  })
  it('falls back to pending for unknown / empty inputs', () => {
    expect(normalizeStatus('')).toBe('pending')
    expect(normalizeStatus('???')).toBe('pending')
    expect(normalizeStatus(null)).toBe('pending')
    expect(normalizeStatus(undefined)).toBe('pending')
  })
})

describe('normalizeType', () => {
  it('maps task type strings', () => {
    expect(normalizeType('interview')).toBe('interview')
    expect(normalizeType('resume_optimize')).toBe('resume_optimize')
    expect(normalizeType('error_coach')).toBe('error_coach')
    expect(normalizeType('general_coach')).toBe('general_coach')
    expect(normalizeType('ability_diagnose')).toBe('ability_diagnose')
  })
  it('returns unknown for non-mapped types', () => {
    expect(normalizeType('foo')).toBe('unknown')
    expect(normalizeType(null)).toBe('unknown')
    expect(normalizeType(undefined)).toBe('unknown')
  })
})

describe('formatDuration', () => {
  it('formats ms / s / m / h sensibly', () => {
    expect(formatDuration(null)).toBe('—')
    expect(formatDuration(0)).toBe('0ms')
    expect(formatDuration(120)).toBe('120ms')
    expect(formatDuration(1500)).toBe('1.50s')
    expect(formatDuration(65_000)).toBe('1m 5s')
    expect(formatDuration(3_725_000)).toBe('1h 2m')
  })
})

describe('computeErrorHash', () => {
  it('returns an 8-char hex when Web Crypto is available', async () => {
    if (typeof globalThis.crypto?.subtle?.digest !== 'function') {
      const h = await computeErrorHash('retry 3 times')
      expect(h).toBe('00000000')
      return
    }
    const h1 = await computeErrorHash('retry 3 times')
    expect(h1).toMatch(/^[0-9a-f]{8}$/)
    // Same input → same hash (stability)
    const h2 = await computeErrorHash('retry 3 times')
    expect(h2).toBe(h1)
  })

  it('strips UUIDs / hex blobs / 12+ digit numbers (FR-022)', async () => {
    if (typeof globalThis.crypto?.subtle?.digest !== 'function') return
    const a = await computeErrorHash('error at uuid 019ec1be-d7c2-7f4a-8b9e-1234567890ab again')
    const b = await computeErrorHash('error at uuid again')
    expect(a).toBe(b)
  })

  it('preserves ordinary 1-11 digit numbers (FR-022 clarification)', async () => {
    if (typeof globalThis.crypto?.subtle?.digest !== 'function') return
    const a = await computeErrorHash('retry 3 times')
    const b = await computeErrorHash('retry 5 times')
    expect(a).not.toBe(b)
  })

  it('does not mutate input', async () => {
    const orig = 'Hello  World  1234'
    await computeErrorHash(orig)
    expect(orig).toBe('Hello  World  1234')
  })
})
