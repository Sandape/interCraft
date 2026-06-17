/**
 * 020 (FIX-011, D-008) — Mock LLM wiring for InterviewLive.
 *
 * When `import.meta.env.VITE_USE_MOCK` is true, the WS hook skips the real
 * backend and emits synthetic events derived from `MOCK_ROUNDS` so the full
 * 5-question flow can be exercised end-to-end without a live LLM key.
 */
import type { WSEvent, InterviewWSState } from './useInterviewWS'
import { MOCK_ROUNDS, MOCK_COMPLETED_EVENT } from '../../tests/e2e/fixtures/mock-llm'

function ts(): string {
  return new Date().toISOString()
}

function toQuestionEvent(roundIdx: number): WSEvent {
  const round = MOCK_ROUNDS[roundIdx]
  const qPayload = round.questionEvent.payload as Record<string, unknown>
  return {
    type: 'node.started',
    event_id: `evt-q-${round.questionNo}-start`,
    session_id: 'mock-session',
    timestamp: ts(),
    node_name: 'question_gen',
    payload: {
      current_question: round.questionNo,
      total_questions: MOCK_ROUNDS.length,
      ...qPayload,
    },
  }
}

function toScoreEvent(roundIdx: number): WSEvent {
  const round = MOCK_ROUNDS[roundIdx]
  const sPayload = round.scoreEvent.payload as Record<string, unknown>
  const score = sPayload.score as number
  return {
    type: 'node.completed',
    event_id: `evt-s-${round.questionNo}`,
    session_id: 'mock-session',
    timestamp: ts(),
    node_name: 'score',
    payload: {
      checkpoint_id: `ckpt-${round.questionNo}`,
      summary: {
        question_no: round.questionNo,
        score,
        dimension: 'tech_depth',
        feedback: sPayload.feedback as string,
        sub_scores: { clarity: score },
      },
    },
  }
}

function toReportEvent(): WSEvent {
  return {
    type: 'node.completed',
    event_id: 'evt-complete',
    session_id: 'mock-session',
    timestamp: ts(),
    node_name: 'report',
    payload: {
      checkpoint_id: 'ckpt-final',
      summary: {
        overall_score: 7,
        report_id: 'mock-report',
      },
    },
  }
}

/** Returns the full ordered event stream for the mock interview. */
export function buildMockEvents(): WSEvent[] {
  const events: WSEvent[] = []
  for (let i = 0; i < MOCK_ROUNDS.length; i++) {
    events.push(toQuestionEvent(i))
    events.push(toScoreEvent(i))
  }
  events.push(toReportEvent())
  return events
}

/** Returns the initial WS state when running in mock mode. */
export function mockInitialState(): InterviewWSState {
  return {
    connected: false,
    reconnecting: false,
    reconnectAttempt: 0,
    currentNode: null,
    currentQuestion: 0,
    totalQuestions: MOCK_ROUNDS.length,
    streamingText: '',
    lastCheckpointId: null,
    error: null,
    events: [],
  }
}

export { MOCK_ROUNDS, MOCK_COMPLETED_EVENT }
