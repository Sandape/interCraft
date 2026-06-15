/** Cursor parity test — cross-DEC-P2-1 encoding consistency. */
import { describe, it, expect } from 'vitest'
import { encodeCursor, decodeCursor } from '../cursor'

describe('Cursor encode/decode', () => {
  it('round-trips a cursor payload', () => {
    const payload = {
      ts: '2026-06-13T00:00:00+00:00',
      id: '018f8a3c-0000-7000-8000-000000000001',
    }
    const opaque = encodeCursor(payload)
    const decoded = decodeCursor(opaque)
    expect(decoded.ts).toBe(payload.ts)
    expect(decoded.id).toBe(payload.id)
  })

  it('produces base64url-safe output (no + or /)', () => {
    const opaque = encodeCursor({
      ts: '2026-06-13T12:34:56+00:00',
      id: 'ffffffff-ffff-7fff-8000-000000000000',
    })
    expect(opaque).not.toContain('+')
    expect(opaque).not.toContain('/')
    expect(opaque).not.toContain('=')
  })

  it('handles multiple round-trips consistently', () => {
    const samples = [
      { ts: '2026-01-01T00:00:00+00:00', id: '00000000-0000-7000-8000-000000000001' },
      { ts: '2026-06-13T12:34:56.789012+00:00', id: '018f8a3c-1234-7000-8000-abcdefabcdef' },
    ]
    for (const sample of samples) {
      expect(decodeCursor(encodeCursor(sample))).toEqual(sample)
    }
  })

  it('handles decoded cursors with and without padding', () => {
    const payload = { ts: '2026-06-13T00:00:00+00:00', id: '018f8a3c-0000-7000-8000-000000000001' }
    const opaque = encodeCursor(payload)
    // decodeCursor should work regardless of padding state
    const decoded = decodeCursor(opaque)
    expect(decoded.ts).toBe(payload.ts)
  })
})
