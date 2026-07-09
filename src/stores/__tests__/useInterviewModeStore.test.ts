/**
 * REQ-048 US1 — Zustand store reset (AC-03).
 *
 * Frontend half of the state-reset contract: after returning to 岗位参数
 * and re-entering the mode selection page, the store must report
 * ``mode === null`` so the user picks a fresh mode.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { useInterviewModeStore, __resetInterviewModeStoreForTests } from '../useInterviewModeStore'

describe('useInterviewModeStore', () => {
  beforeEach(() => {
    __resetInterviewModeStoreForTests()
  })

  it('starts with null mode', () => {
    expect(useInterviewModeStore.getState().mode).toBeNull()
  })

  it('setMode updates mode', () => {
    useInterviewModeStore.getState().setMode('full')
    expect(useInterviewModeStore.getState().mode).toBe('full')
  })

  it('setMode clears subMode', () => {
    useInterviewModeStore.getState().setSubMode('quick_drill')
    expect(useInterviewModeStore.getState().subMode).toBe('quick_drill')
    useInterviewModeStore.getState().setMode('doubao')
    expect(useInterviewModeStore.getState().subMode).toBeNull()
  })

  it('reset() returns to initial state (AC-03)', () => {
    useInterviewModeStore.getState().setMode('full')
    useInterviewModeStore.getState().setMaxQuestions(15)
    useInterviewModeStore.getState().setUseVariants(true)
    expect(useInterviewModeStore.getState().mode).toBe('full')
    expect(useInterviewModeStore.getState().maxQuestions).toBe(15)
    expect(useInterviewModeStore.getState().useVariants).toBe(true)

    useInterviewModeStore.getState().reset()

    expect(useInterviewModeStore.getState().mode).toBeNull()
    expect(useInterviewModeStore.getState().maxQuestions).toBeNull()
    expect(useInterviewModeStore.getState().useVariants).toBe(false)
    expect(useInterviewModeStore.getState().subMode).toBeNull()
  })

  it('default useVariants is false (AC-25 / R22)', () => {
    expect(useInterviewModeStore.getState().useVariants).toBe(false)
  })
})