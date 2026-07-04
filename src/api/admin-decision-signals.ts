/**
 * Admin Console Command Center / Decision Signals API client —
 * REQ-044 US1.
 *
 * Endpoints:
 *
 * - GET /api/v1/admin-console/command-center/signals?limit=
 * - GET /api/v1/admin-console/command-center/overview
 * - GET /api/v1/admin-console/command-center/health
 *
 * The backend router is mounted by ``backend/app/main.py`` at prefix
 * ``/api/v1/admin-console/command-center``.
 */
import { apiClient } from './client'
import type {
  CommandCenterOverviewResponse,
  DecisionSignalListResponse,
} from '../types/admin-decision-signals'

const BASE = '/api/v1/admin-console/command-center'

export interface DecisionSignalsListParams {
  limit?: number
}

export const adminCommandCenterApi = {
  /** FR-007~FR-010 — prioritized decision-signal queue. */
  listSignals: (
    params: DecisionSignalsListParams = {},
    signal?: AbortSignal,
  ) =>
    apiClient.request<DecisionSignalListResponse>({
      method: 'GET',
      path: `${BASE}/signals`,
      query: {
        limit: params.limit ?? 50,
      },
      signal,
    }),

  /** 4 KPI tiles for the workspace header. */
  getOverview: (signal?: AbortSignal) =>
    apiClient.request<CommandCenterOverviewResponse>({
      method: 'GET',
      path: `${BASE}/overview`,
      signal,
    }),

  /** Module liveness. */
  getHealth: (signal?: AbortSignal) =>
    apiClient.request<{ status: string; module: string }>({
      method: 'GET',
      path: `${BASE}/health`,
      signal,
    }),
}