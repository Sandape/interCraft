/** React Query hooks for jobs (US8). */
import { useQuery } from '@tanstack/react-query'
import type { Job, JobStats, JobTimelineEntry } from '../../repositories/JobRepository'
import { getJobRepository } from '../../repositories/types'

export function useJobs(params?: { status?: string; limit?: number }) {
  return useQuery({
    queryKey: ['jobs', params],
    queryFn: () => getJobRepository().list(params),
    staleTime: 30_000,
  })
}

export function useJob(id: string) {
  return useQuery<Job>({
    queryKey: ['job', id],
    queryFn: () => getJobRepository().get(id),
    staleTime: 30_000,
    enabled: !!id,
  })
}

export function useJobStats() {
  return useQuery<JobStats>({
    queryKey: ['jobStats'],
    queryFn: () => getJobRepository().stats(),
    staleTime: 30_000,
  })
}

export function useJobTimeline(id: string) {
  return useQuery<{ data: JobTimelineEntry[] }>({
    queryKey: ['jobTimeline', id],
    queryFn: () => getJobRepository().timeline(id),
    staleTime: 60_000,
    enabled: !!id,
  })
}
