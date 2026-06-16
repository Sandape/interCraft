/**
 * T061 — Mock LLM response fixture for E2E 5-step cross-module linking test.
 *
 * Provides typed mock question / score / answer payloads so the Playwright
 * spec can intercept and respond over WebSocket, simulating a full 5-round
 * interview without calling DeepSeek.
 *
 * Usage:
 *   import { MOCK_ROUNDS } from '../fixtures/mock-llm'
 *   page.routeWebSocket with ws:// path to intercept interview WS
 */

export interface MockRound {
  questionNo: number
  questionText: string
  rawScore: number
  /** Full question-generated event payload. */
  questionEvent: Record<string, unknown>
  /** Full score event payload (triggered after answer is submitted). */
  scoreEvent: Record<string, unknown>
}

/** 5 mock rounds — round 2 has rawScore=3.5 (<6) to trigger error-book sink. */
export const MOCK_ROUNDS: MockRound[] = [
  {
    questionNo: 1,
    questionText: '请解释 React 中 useMemo 和 useCallback 的区别及使用场景。',
    rawScore: 8.0,
    questionEvent: {
      type: 'question_generated',
      event_id: 'evt-q-1',
      session_id: 'mock-session',
      timestamp: new Date().toISOString(),
      node_name: 'question_gen',
      payload: {
        question_no: 1,
        question_text: '请解释 React 中 useMemo 和 useCallback 的区别及使用场景。',
        total_questions: 5,
      },
    },
    scoreEvent: {
      type: 'question_scored',
      event_id: 'evt-s-1',
      session_id: 'mock-session',
      timestamp: new Date().toISOString(),
      node_name: 'score',
      payload: {
        question_no: 1,
        raw_score: 8.0,
        score: 8,
        feedback: '回答清晰,对 memoization 理解到位。建议补充依赖数组对比机制的细节。',
        reference_answer: '',
      },
    },
  },
  {
    questionNo: 2,
    questionText: '描述 React 的 Fiber 架构是如何实现增量渲染的。',
    rawScore: 3.5,
    questionEvent: {
      type: 'question_generated',
      event_id: 'evt-q-2',
      session_id: 'mock-session',
      timestamp: new Date().toISOString(),
      node_name: 'question_gen',
      payload: {
        question_no: 2,
        question_text: '描述 React 的 Fiber 架构是如何实现增量渲染的。',
        total_questions: 5,
      },
    },
    scoreEvent: {
      type: 'question_scored',
      event_id: 'evt-s-2',
      session_id: 'mock-session',
      timestamp: new Date().toISOString(),
      node_name: 'score',
      payload: {
        question_no: 2,
        raw_score: 3.5,
        score: 3,
        feedback: '对 Fiber 的理解较浅,未能解释 workInProgress 树和双缓冲机制。建议重点复习。',
        reference_answer: 'Fiber 架构通过链表结构实现增量渲染...',
      },
    },
  },
  {
    questionNo: 3,
    questionText: 'Redux 和 Zustand 在状态管理上的设计理念有何不同?',
    rawScore: 7.5,
    questionEvent: {
      type: 'question_generated',
      event_id: 'evt-q-3',
      session_id: 'mock-session',
      timestamp: new Date().toISOString(),
      node_name: 'question_gen',
      payload: {
        question_no: 3,
        question_text: 'Redux 和 Zustand 在状态管理上的设计理念有何不同?',
        total_questions: 5,
      },
    },
    scoreEvent: {
      type: 'question_scored',
      event_id: 'evt-s-3',
      session_id: 'mock-session',
      timestamp: new Date().toISOString(),
      node_name: 'score',
      payload: {
        question_no: 3,
        raw_score: 7.5,
        score: 8,
        feedback: '对 flux 模式理解正确。可以补充 atomic selectors 和订阅粒度的对比。',
        reference_answer: '',
      },
    },
  },
  {
    questionNo: 4,
    questionText: '如何优化 React 应用的首屏加载性能?',
    rawScore: 6.5,
    questionEvent: {
      type: 'question_generated',
      event_id: 'evt-q-4',
      session_id: 'mock-session',
      timestamp: new Date().toISOString(),
      node_name: 'question_gen',
      payload: {
        question_no: 4,
        question_text: '如何优化 React 应用的首屏加载性能?',
        total_questions: 5,
      },
    },
    scoreEvent: {
      type: 'question_scored',
      event_id: 'evt-s-4',
      session_id: 'mock-session',
      timestamp: new Date().toISOString(),
      node_name: 'score',
      payload: {
        question_no: 4,
        raw_score: 6.5,
        score: 7,
        feedback: '提到了 code splitting 和 lazy loading,可以再深入 service worker 和 streaming SSR。',
        reference_answer: '',
      },
    },
  },
  {
    questionNo: 5,
    questionText: 'React 18 的并发模式(Concurrent Features)解决了什么核心问题?',
    rawScore: 9.0,
    questionEvent: {
      type: 'question_generated',
      event_id: 'evt-q-5',
      session_id: 'mock-session',
      timestamp: new Date().toISOString(),
      node_name: 'question_gen',
      payload: {
        question_no: 5,
        question_text: 'React 18 的并发模式(Concurrent Features)解决了什么核心问题?',
        total_questions: 5,
      },
    },
    scoreEvent: {
      type: 'question_scored',
      event_id: 'evt-s-5',
      session_id: 'mock-session',
      timestamp: new Date().toISOString(),
      node_name: 'score',
      payload: {
        question_no: 5,
        raw_score: 9.0,
        score: 9,
        feedback: '对并发渲染理解深刻。建议关注 useTransition 在实际场景中的使用。',
        reference_answer: '',
      },
    },
  },
]

/** Minimal mock events for the interview to reach "completed" state. */
export const MOCK_COMPLETED_EVENT: Record<string, unknown> = {
  type: 'interview_completed',
  event_id: 'evt-complete',
  session_id: 'mock-session',
  timestamp: new Date().toISOString(),
  node_name: 'report',
  payload: {
    status: 'completed',
  },
}

/** Mock token for the seeded user (valid for 24h). */
export const MOCK_REGISTER_USER = {
  email: `e2e-019-${Date.now()}@intercraft-e2e.com`,
  password: 'P@ssw0rd1234',
  display_name: 'E2E 019 联动冒烟',
}

export const API_BASE = process.env.E2E_API_BASE ?? 'http://127.0.0.1:8000'
export const WS_BASE = process.env.E2E_WS_BASE ?? 'ws://127.0.0.1:8000'
