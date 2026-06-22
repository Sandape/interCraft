/**
 * 021 — Error Coach scenario writer + preset scenarios.
 *
 * The MockLLMClient (backend/app/agents/llm_client_mock.py) reads a scenario
 * JSON file at startup. The path is passed to the backend via the
 * LLM_MOCK_SCENARIO_PATH env var. Because the backend is started once per
 * E2E session (not per test), we write to a FIXED path before each test and
 * the mock client re-reads the file on every invoke — so each test sees the
 * scenario it wrote.
 *
 * Scenario JSON shape:
 *   {
 *     "evaluate_scores":  [8, 9, 9],          // popped in order by error_coach_evaluate
 *     "hint_contents":    {                    // keyed by hint level
 *       "small":   "...",
 *       "medium":  "...",
 *       "detailed": "..."
 *     }
 *   }
 *
 * The mock client falls back to score=5 / empty hint if a sequence is
 * exhausted or a level is missing.
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export interface ErrorCoachScenario {
  evaluate_scores: number[]
  hint_contents: {
    small: string
    medium: string
    detailed: string
  }
}

/**
 * Fixed absolute path the backend reads from. Must match the
 * LLM_MOCK_SCENARIO_PATH env var used to start the backend for E2E.
 */
export const SCENARIO_FILE_PATH = resolve(
  __dirname,
  'error-coach-scenarios',
  'active.json',
)

/** HAPPY-01: 3 correct in a row → completed, frequency 3 → 2. */
export const HAPPY_SCENARIO: ErrorCoachScenario = {
  evaluate_scores: [8, 9, 9],
  hint_contents: {
    small: '提示：回忆 React Hooks 的依赖数组机制。',
    medium: '中等提示：对比 useMemo 与 useCallback 的输入输出。',
    detailed: '详细提示：useMemo 缓存值，useCallback 缓存函数实例。',
  },
}

/** EDGE-01: 1 wrong + 3 correct → completed after round 4, frequency 3 → 2. */
export const EDGE_1W_3C_SCENARIO: ErrorCoachScenario = {
  evaluate_scores: [5, 9, 9, 9],
  hint_contents: {
    small: '提示：思考 React Hooks 的依赖数组。',
    medium: '中等提示：useMemo 与 useCallback 的区别。',
    detailed: '详细提示：useMemo 缓存值，useCallback 缓存函数。',
  },
}

/** ABORT-01: 1 correct then abort → aborted, correct_count_achieved=1, frequency 3 → 2. */
export const ABORT_AFTER_1_SCENARIO: ErrorCoachScenario = {
  evaluate_scores: [9],
  hint_contents: {
    small: '提示：回忆 Hooks 依赖。',
    medium: '中等提示。',
    detailed: '详细提示。',
  },
}

/**
 * Write a scenario to the fixed active.json path. The backend's MockLLMClient
 * re-reads the file on every invoke, so writing before each test is enough.
 */
export function writeScenarioFile(scenario: ErrorCoachScenario): string {
  mkdirSync(dirname(SCENARIO_FILE_PATH), { recursive: true })
  writeFileSync(SCENARIO_FILE_PATH, JSON.stringify(scenario, null, 2), 'utf-8')
  return SCENARIO_FILE_PATH
}
