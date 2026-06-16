/** Jobs API service — typed wrappers around the jobs endpoints. */
import { apiClient } from './client'
import type { JobTransitionsResponse } from '@/types/jobs'

export async function getJobTransitions(): Promise<JobTransitionsResponse> {
  return apiClient.request<JobTransitionsResponse>(
    'GET',
    '/api/v1/jobs/transitions',
  )
}
