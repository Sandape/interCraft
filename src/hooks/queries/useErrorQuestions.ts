/** React Query hooks for error questions (US6). */
import { useQuery } from '@tanstack/react-query'
import type { ErrorQuestion } from '../../repositories/ErrorQuestionRepository'
import { getErrorQuestionRepository } from '../../repositories/types'

export function useErrorQuestions(params?: {
  dimension?: string; status?: string; frequency_min?: number; limit?: number
}) {
  return useQuery({
    queryKey: ['errorQuestions', params],
    queryFn: () => getErrorQuestionRepository().list(params),
    staleTime: 30_000,
  })
}

export function useErrorQuestion(id: string) {
  return useQuery<ErrorQuestion>({
    queryKey: ['errorQuestion', id],
    queryFn: () => getErrorQuestionRepository().get(id),
    staleTime: 30_000,
    enabled: !!id,
  })
}
