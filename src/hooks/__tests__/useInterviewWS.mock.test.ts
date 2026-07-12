/* 020 (FIX-011, D-008) — Phase 4 Mock LLM must be wired into the WS hook.
 *
 * Round-1 evidence: `tests/e2e/fixtures/mock-llm.ts` defines `MOCK_ROUNDS`,
 * but no source code reads it. With no live LLM key, the interview flow
 * cannot be E2E-tested or run end-to-end in dev (VITE_USE_MOCK=true).
 *
 * The fix:
 *   1. `src/hooks/useInterviewWS.mock.ts` builds the WSEvent stream from
 *      MOCK_ROUNDS.
 *   2. `useInterviewWS` short-circuits to the mock emitter when
 *      `import.meta.env.VITE_USE_MOCK === 'true'`.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useInterviewWS } from '@/hooks/useInterviewWS'
import { buildMockEvents, mockInitialState, MOCK_ROUNDS } from '@/hooks/useInterviewWS.mock'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllEnvs()
})

describe('mockInterviewStream — event builder (020 D-008)', () => {
  it('builds 11 events: 5 questions + 5 scores + 1 report', () => {
    const events = buildMockEvents()
    // 5 question_start + 5 score_completed + 1 report_completed
    expect(events.length).toBe(MOCK_ROUNDS.length * 2 + 1)
  })

  it('emits score and question events in alternating order per round', () => {
    const events = buildMockEvents()
    // First 2 events should be question + score for round 1
    expect(events[0].node_name).toBe('question_gen')
    expect(events[1].node_name).toBe('score')
    // Last event is the report
    expect(events[events.length - 1].node_name).toBe('report')
  })

  it('score payload carries the question_no and dimension', () => {
    const events = buildMockEvents()
    const round1Score = events[1]
    expect(round1Score.payload.summary.question_no).toBe(1)
    expect(round1Score.payload.summary.dimension).toBe('tech_depth')
    expect(round1Score.payload.summary.score).toBe(8)
  })

  it('mockInitialState returns every required InterviewWSState field', () => {
    const state = mockInitialState()
    // Connection fields
    expect(state.connected).toBe(false)
    expect(state.reconnecting).toBe(false)
    expect(state.reconnectAttempt).toBe(0)
    // Runtime fields
    expect(state.currentNode).toBeNull()
    expect(state.currentQuestion).toBe(0)
    expect(state.totalQuestions).toBe(MOCK_ROUNDS.length)
    expect(state.streamingText).toBe('')
    expect(state.lastCheckpointId).toBeNull()
    expect(state.error).toBeNull()
    expect(state.events).toEqual([])
    expect(state.turnPhase).toBe('idle')
    // US4 runtime-envelope fields (REQ-061)
    expect(state.taskId).toBeNull()
    expect(state.executionId).toBeNull()
    expect(state.availableActions).toEqual([])
    expect(state.pointsSummary).toBeNull()
    // Reconnect-state tracking
    expect(state.seenSequences).toEqual([])
  })
})

describe('useInterviewWS — VITE_USE_MOCK branch (020 D-008)', () => {
  it('skips real WebSocket and feeds events from MOCK_ROUNDS when VITE_USE_MOCK=true', async () => {
    // 020 (FIX-011, D-008) — Vitest cannot easily stub import.meta.env for
    // Vite-bundled modules. The hook accepts a `globalThis.__VITE_USE_MOCK_OVERRIDE__`
    // escape hatch that this test uses to force the mock path.
    ;(globalThis as any).__VITE_USE_MOCK_OVERRIDE__ = 'true'
    const wsSpy = vi.spyOn(globalThis, 'WebSocket' as any)

    const { result } = renderHook(() => useInterviewWS('mock-token'))

    act(() => {
      result.current.connect()
    })

    // No real WebSocket was constructed
    expect(wsSpy).not.toHaveBeenCalled()

    // Connected flag flips on synchronously (mock stream is "always up")
    expect(result.current.state.connected).toBe(true)

    // After at least one round, the events buffer should contain a question_gen event
    expect(result.current.state.events.some((e) => e.node_name === 'question_gen')).toBe(true)

    delete (globalThis as any).__VITE_USE_MOCK_OVERRIDE__
  })
})
