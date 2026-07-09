/** Shared TypeScript types for the Jobs module. */

/** REQ-053: new 7-state model. Source of truth is `GET /api/v1/jobs/transitions`. */
export const INTERVIEW_STATUSES = ['test', 'interview_1', 'interview_2', 'interview_3'] as const
export type InterviewStatus = (typeof INTERVIEW_STATUSES)[number]

/** Terminal states: advancement is blocked (T027). */
export const TERMINAL_JOB_STATUSES = ['failed', 'passed'] as const
export type TerminalJobStatus = (typeof TERMINAL_JOB_STATUSES)[number]

/** Human-readable Chinese labels for every job status. Used by popover, tabs, badge, timeline. */
export const JOB_STATUS_LABELS: Record<string, string> = {
  applied: '已投递',
  test: '笔试中',
  interview_1: '一面中',
  interview_2: '二面中',
  interview_3: '三面中',
  failed: '已失败',
  passed: '已通过',
}

export function isInterviewStatus(s: string): s is InterviewStatus {
  return (INTERVIEW_STATUSES as readonly string[]).includes(s)
}

export function isTerminalStatus(s: string): s is TerminalJobStatus {
  return (TERMINAL_JOB_STATUSES as readonly string[]).includes(s)
}

export interface JobTransitionEdge {
  from: string
  to: string
}

export interface JobTransitionsResponse {
  statuses: string[]
  transitions: JobTransitionEdge[]
}
