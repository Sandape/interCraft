/**
 * Admin Console / Privacy-Safe User Lookup API client — REQ-044 US2.
 *
 * Endpoints:
 *
 * - GET /api/v1/admin-console/users/{user_id} — FR-015.
 *
 * The response schema (UserPrivacySafe) is the FR-032 privacy
 * allow-list — it MUST NOT contain raw_resume / raw_interview_answer
 * / raw_prompt / raw_model_output. AC-15.4 grep gate verifies the
 * frontend page that renders this response.
 */
import { apiClient } from './client'
import type { UserPrivacySafe } from '../types/admin-product-analytics'

const BASE = '/api/v1/admin-console/users'

export const adminUsersApi = {
  /** FR-015 — privacy-safe profile for ``user_id``. */
  getUserSafe: (userId: string, signal?: AbortSignal) =>
    apiClient.request<UserPrivacySafe>({
      method: 'GET',
      path: `${BASE}/${encodeURIComponent(userId)}`,
      signal,
    }),
}