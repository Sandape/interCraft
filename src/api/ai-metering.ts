/**
 * REQ-061 (US8) — AI Points / metering user API client.
 *
 * Paths follow `specs/061-ai-agent-production/contracts/ai-metering.openapi.yaml`
 * (server base `/api/v1`). Types come from generated OpenAPI output.
 * No RMB / purchase / recharge operations belong to this surface.
 */
import { apiClient } from './client'
import type {
  ExportAIPointLedgerBody,
  ExportJob,
  LedgerPage,
  ListAIPointLedgerQuery,
  PointAccount,
  PointBudget,
  UpdateAIPointBudgetBody,
} from '@/types/ai-metering'

const BASE = '/api/v1'

function idempotencyHeaders(idempotencyKey: string): Record<string, string> {
  return { 'Idempotency-Key': idempotencyKey }
}

/** GET /ai-points/account */
export async function getAIPointAccount(
  signal?: AbortSignal,
): Promise<PointAccount> {
  return apiClient.request<PointAccount>({
    method: 'GET',
    path: `${BASE}/ai-points/account`,
    signal,
  })
}

/** GET /ai-points/ledger */
export async function listAIPointLedger(
  query: ListAIPointLedgerQuery = {},
  signal?: AbortSignal,
): Promise<LedgerPage> {
  return apiClient.request<LedgerPage>({
    method: 'GET',
    path: `${BASE}/ai-points/ledger`,
    query: {
      event_type: query.event_type,
      task_id: query.task_id,
      from: query.from,
      to: query.to,
      cursor: query.cursor,
      limit: query.limit,
    },
    signal,
  })
}

/** POST /ai-points/ledger/export */
export async function exportAIPointLedger(
  body: ExportAIPointLedgerBody,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<ExportJob> {
  return apiClient.request<ExportJob>({
    method: 'POST',
    path: `${BASE}/ai-points/ledger/export`,
    body,
    headers: idempotencyHeaders(idempotencyKey),
    signal,
  })
}

/** GET /ai-points/budget */
export async function getAIPointBudget(
  signal?: AbortSignal,
): Promise<PointBudget> {
  return apiClient.request<PointBudget>({
    method: 'GET',
    path: `${BASE}/ai-points/budget`,
    signal,
  })
}

/** PATCH /ai-points/budget */
export async function updateAIPointBudget(
  body: UpdateAIPointBudgetBody,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<PointBudget> {
  return apiClient.request<PointBudget>({
    method: 'PATCH',
    path: `${BASE}/ai-points/budget`,
    body,
    headers: idempotencyHeaders(idempotencyKey),
    signal,
  })
}

export const aiMeteringApi = {
  getAIPointAccount,
  listAIPointLedger,
  exportAIPointLedger,
  getAIPointBudget,
  updateAIPointBudget,
}
