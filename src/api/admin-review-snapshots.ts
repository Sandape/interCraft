/**
 * Admin Console Review Snapshots API client — REQ-044 US7.
 *
 * Endpoints (mounted by backend/app/main.py at
 * `/api/v1/admin-console/review-snapshots`):
 *
 * - POST   /api/v1/admin-console/review-snapshots            — generate snapshot
 * - GET    /api/v1/admin-console/review-snapshots            — list snapshots
 * - GET    /api/v1/admin-console/review-snapshots/{id}       — get with fresh current_values
 * - GET    /api/v1/admin-console/review-snapshots/health     — module liveness
 *
 * PUT/PATCH/DELETE return 405 SNAPSHOT_IMMUTABLE (AC-30.4) — not exposed here.
 */
import { apiClient } from './client'
import type {
  ReviewSnapshotListResponse,
  ReviewSnapshotRequest,
  ReviewSnapshotResponse,
} from '../types/admin-review-snapshots'

const BASE = '/api/v1/admin-console/review-snapshots'

export const adminReviewSnapshotsApi = {
  /** FR-029 AC-29.1 — generate snapshot (POST). */
  create: (body: ReviewSnapshotRequest, signal?: AbortSignal) =>
    apiClient.request<ReviewSnapshotResponse>({
      method: 'POST',
      path: BASE,
      body,
      signal,
    }),

  /** FR-029 — list snapshots (GET). */
  list: (signal?: AbortSignal) =>
    apiClient.request<ReviewSnapshotListResponse>({
      method: 'GET',
      path: BASE,
      signal,
    }),

  /** FR-030 AC-30.1 — get snapshot with fresh current_values + delta (GET). */
  get: (snapshotId: string, signal?: AbortSignal) =>
    apiClient.request<ReviewSnapshotResponse>({
      method: 'GET',
      path: `${BASE}/${snapshotId}`,
      signal,
    }),
}