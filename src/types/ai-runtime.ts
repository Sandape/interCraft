/**
 * Convenience aliases over generated OpenAPI schemas (REQ-061).
 * Source of truth: `src/types/generated/ai-runtime.ts` from
 * `specs/061-ai-agent-production/contracts/ai-runtime.openapi.yaml`.
 */
import type { components, operations } from './generated/ai-runtime'

export type TaskStatus = components['schemas']['TaskStatus']
export type ServiceTier = components['schemas']['ServiceTier']
export type AvailableAction = components['schemas']['AvailableAction']
export type QuoteRequest = components['schemas']['QuoteRequest']
export type MilestoneQuote = components['schemas']['MilestoneQuote']
export type PointQuote = components['schemas']['PointQuote']
export type TaskAccepted = components['schemas']['TaskAccepted']
export type Stage = components['schemas']['Stage']
export type TaskSummary = components['schemas']['TaskSummary']
export type PointSummary = components['schemas']['PointSummary']
export type TaskPage = components['schemas']['TaskPage']
export type Milestone = components['schemas']['Milestone']
export type ExecutionRef = components['schemas']['ExecutionRef']
export type FailurePresentation = components['schemas']['FailurePresentation']
export type TaskDetail = components['schemas']['TaskDetail']
export type TaskEvent = components['schemas']['TaskEvent']
export type TaskActionRequest = components['schemas']['TaskActionRequest']
export type ResumeRequest = components['schemas']['ResumeRequest']
export type ReexecutionRequest = components['schemas']['ReexecutionRequest']
export type Problem = components['schemas']['Problem']

export type ListAITasksQuery = NonNullable<operations['listAITasks']['parameters']['query']>
export type TaskEventsPage = operations['listAITaskEvents']['responses'][200]['content']['application/json']
export type SettlementStatus = PointSummary['settlement_status']
export type MilestoneStatus = Milestone['status']
