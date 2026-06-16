/** React Query hooks for interview sessions (US4 partial). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { InterviewSession, CreateInterviewSessionInput } from '../../repositories/InterviewSessionRepository'
import { getInterviewSessionRepository } from '../../repositories/types'

export function useInterviewSessions(params?: { status?: string; limit?: number }) {
  return useQuery({
    queryKey: ['interviewSessions', params],
    queryFn: () => getInterviewSessionRepository().list(params),
    staleTime: 30_000,
  })
}

export function useInterviewSession(id: string) {
  return useQuery<InterviewSession>({
    queryKey: ['interviewSession', id],
    queryFn: () => getInterviewSessionRepository().get(id),
    staleTime: 30_000,
    enabled: !!id,
  })
}

// 019 — Create-from-Job mutation (US3, FR-014)
export function useCreateInterviewFromJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { jobId: string; branchId: string | null }) =>
      getInterviewSessionRepository().create({
        position: '',  // resolved server-side from the job
        company: '',
        branch_id: input.branchId,
        job_id: input.jobId,
      }),
    onSuccess: (session) => {
      queryClient.invalidateQueries({ queryKey: ['interviewSessions'] })
      return session
    },
  })
}

export function useCreateInterviewSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateInterviewSessionInput) =>
      getInterviewSessionRepository().create(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['interviewSessions'] })
    },
  })
}

export function useDeleteInterviewSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => getInterviewSessionRepository().delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['interviewSessions'] })
    },
  })
}

