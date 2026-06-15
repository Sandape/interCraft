/** React Query hooks for interview sessions (US4 partial). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { InterviewSession } from '../../repositories/InterviewSessionRepository'
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

export function useDeleteInterviewSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => getInterviewSessionRepository().delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['interviewSessions'] })
    },
  })
}

