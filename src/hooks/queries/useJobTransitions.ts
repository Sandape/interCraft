/** useJobTransitions — fetch the canonical JOB_TRANSITIONS graph. */
import { useQuery } from '@tanstack/react-query'
import { getJobTransitions } from '@/api/jobs'
import type { JobTransitionsResponse } from '@/types/jobs'

/** Fallback when the API is unreachable — preserves UI shape, drives the
 *  "stale" banner. The 7 statuses and 20 edges mirror backend `JOB_TRANSITIONS`. */
const FALLBACK: JobTransitionsResponse = {
  statuses: ['applied', 'test', 'oa', 'hr', 'offer', 'rejected', 'withdrawn'],
  transitions: [
    { from: 'applied', to: 'test' },
    { from: 'applied', to: 'oa' },
    { from: 'applied', to: 'hr' },
    { from: 'applied', to: 'offer' },
    { from: 'applied', to: 'rejected' },
    { from: 'applied', to: 'withdrawn' },
    { from: 'test', to: 'oa' },
    { from: 'test', to: 'hr' },
    { from: 'test', to: 'offer' },
    { from: 'test', to: 'rejected' },
    { from: 'test', to: 'withdrawn' },
    { from: 'oa', to: 'hr' },
    { from: 'oa', to: 'offer' },
    { from: 'oa', to: 'rejected' },
    { from: 'oa', to: 'withdrawn' },
    { from: 'hr', to: 'offer' },
    { from: 'hr', to: 'rejected' },
    { from: 'hr', to: 'withdrawn' },
    { from: 'offer', to: 'rejected' },
    { from: 'offer', to: 'withdrawn' },
  ],
}

export function useJobTransitions() {
  const q = useQuery({
    queryKey: ['jobTransitions'],
    queryFn: getJobTransitions,
    staleTime: Infinity,
    gcTime: Infinity,
    retry: 1,
  })
  return {
    data: q.data ?? FALLBACK,
    isStale: q.isError,
    isLoading: q.isLoading,
    refetch: q.refetch,
  }
}
