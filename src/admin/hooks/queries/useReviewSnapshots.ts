/**
 * React Query hooks for the Review Snapshots workspace (REQ-044 US7).
 *
 * - useReviewSnapshots — list
 * - useReviewSnapshot — single with fresh current_values + delta
 * - useCreateReviewSnapshot — generate mutation
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { adminReviewSnapshotsApi } from '@/api/admin-review-snapshots'
import type { ReviewSnapshotRequest } from '@/types/admin-review-snapshots'

// ---------------------------------------------------------------------------
// Query keys (centralized so mutations can invalidate cleanly)
// ---------------------------------------------------------------------------

export const reviewSnapshotsKeys = {
  all: ['admin-console', 'review-snapshots'] as const,
  list: () => [...reviewSnapshotsKeys.all, 'list'] as const,
  detail: (id: string) => [...reviewSnapshotsKeys.all, 'detail', id] as const,
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function useReviewSnapshots() {
  return useQuery({
    queryKey: reviewSnapshotsKeys.list(),
    queryFn: ({ signal }) => adminReviewSnapshotsApi.list(),
    staleTime: 60_000,
  })
}

export function useReviewSnapshot(snapshotId: string) {
  return useQuery({
    queryKey: reviewSnapshotsKeys.detail(snapshotId),
    queryFn: ({ signal }) => adminReviewSnapshotsApi.get(snapshotId),
    staleTime: 30_000,
    enabled: Boolean(snapshotId),
  })
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useCreateReviewSnapshot() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: ReviewSnapshotRequest) =>
      adminReviewSnapshotsApi.create(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: reviewSnapshotsKeys.list() })
    },
  })
}