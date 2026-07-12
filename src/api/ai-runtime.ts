/**
 * REQ-061 (US1) — AI Runtime user API client.
 *
 * Paths follow `specs/061-ai-agent-production/contracts/ai-runtime.openapi.yaml`
 * (server base `/api/v1`). Types come from generated OpenAPI output.
 */
import { apiClient } from './client'
import type {
  ListAITasksQuery,
  PointQuote,
  QuoteRequest,
  ReexecutionRequest,
  ResumeRequest,
  TaskAccepted,
  TaskActionRequest,
  TaskDetail,
  TaskEventsPage,
  TaskPage,
} from '@/types/ai-runtime'

const BASE = '/api/v1'

function idempotencyHeaders(idempotencyKey: string): Record<string, string> {
  return { 'Idempotency-Key': idempotencyKey }
}

/** POST /ai-task-quotes */
export async function createAITaskQuote(
  body: QuoteRequest,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<PointQuote> {
  return apiClient.request<PointQuote>({
    method: 'POST',
    path: `${BASE}/ai-task-quotes`,
    body,
    headers: idempotencyHeaders(idempotencyKey),
    signal,
  })
}

/** GET /ai-tasks */
export async function listAITasks(
  query: ListAITasksQuery = {},
  signal?: AbortSignal,
): Promise<TaskPage> {
  return apiClient.request<TaskPage>({
    method: 'GET',
    path: `${BASE}/ai-tasks`,
    query: {
      capability: query.capability,
      status: query.status,
      settlement: query.settlement,
      from: query.from,
      to: query.to,
      cursor: query.cursor,
      limit: query.limit,
    },
    signal,
  })
}

/** GET /ai-tasks/{taskId} */
export async function getAITask(
  taskId: string,
  signal?: AbortSignal,
): Promise<TaskDetail> {
  return apiClient.request<TaskDetail>({
    method: 'GET',
    path: `${BASE}/ai-tasks/${taskId}`,
    signal,
  })
}

export interface ListAITaskEventsParams {
  after_sequence?: number
  limit?: number
}

/** GET /ai-tasks/{taskId}/events */
export async function listAITaskEvents(
  taskId: string,
  params: ListAITaskEventsParams = {},
  signal?: AbortSignal,
): Promise<TaskEventsPage> {
  return apiClient.request<TaskEventsPage>({
    method: 'GET',
    path: `${BASE}/ai-tasks/${taskId}/events`,
    query: {
      after_sequence: params.after_sequence,
      limit: params.limit,
    },
    signal,
  })
}

/** POST /ai-tasks/{taskId}/cancel */
export async function cancelAITask(
  taskId: string,
  body: TaskActionRequest,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<TaskAccepted> {
  return apiClient.request<TaskAccepted>({
    method: 'POST',
    path: `${BASE}/ai-tasks/${taskId}/cancel`,
    body,
    headers: idempotencyHeaders(idempotencyKey),
    signal,
  })
}

/** POST /ai-tasks/{taskId}/resume */
export async function resumeAITask(
  taskId: string,
  body: ResumeRequest,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<TaskAccepted> {
  return apiClient.request<TaskAccepted>({
    method: 'POST',
    path: `${BASE}/ai-tasks/${taskId}/resume`,
    body,
    headers: idempotencyHeaders(idempotencyKey),
    signal,
  })
}

/** POST /ai-tasks/{taskId}/system-failure-retry */
export async function retrySystemFailedAITask(
  taskId: string,
  body: TaskActionRequest,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<TaskAccepted> {
  return apiClient.request<TaskAccepted>({
    method: 'POST',
    path: `${BASE}/ai-tasks/${taskId}/system-failure-retry`,
    body,
    headers: idempotencyHeaders(idempotencyKey),
    signal,
  })
}

/** POST /ai-tasks/{taskId}/re-executions */
export async function reexecuteAITask(
  taskId: string,
  body: ReexecutionRequest,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<TaskAccepted> {
  return apiClient.request<TaskAccepted>({
    method: 'POST',
    path: `${BASE}/ai-tasks/${taskId}/re-executions`,
    body,
    headers: idempotencyHeaders(idempotencyKey),
    signal,
  })
}

export const aiRuntimeApi = {
  createAITaskQuote,
  listAITasks,
  getAITask,
  listAITaskEvents,
  cancelAITask,
  resumeAITask,
  retrySystemFailedAITask,
  reexecuteAITask,
}
