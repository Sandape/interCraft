/** Mutation hooks for error questions (US6). */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { ErrorQuestion } from '../../repositories/ErrorQuestionRepository'
import { getErrorQuestionRepository } from '../../repositories/types'

export function useCreateErrorQuestion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: { question_text: string; dimension?: string; answer_text?: string }) =>
      getErrorQuestionRepository().create(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['errorQuestions'] })
    },
  })
}

export function useUpdateErrorQuestion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Record<string, unknown> }) =>
      getErrorQuestionRepository().patch(id, patch),
    onSuccess: (data: ErrorQuestion) => {
      qc.setQueryData(['errorQuestion', data.id], data)
      qc.invalidateQueries({ queryKey: ['errorQuestions'] })
    },
  })
}

export function useArchiveErrorQuestion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => getErrorQuestionRepository().archive(id),
    onSuccess: (_data, id) => {
      qc.removeQueries({ queryKey: ['errorQuestion', id] })
      qc.invalidateQueries({ queryKey: ['errorQuestions'] })
    },
  })
}

export function useResetErrorQuestion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => getErrorQuestionRepository().reset(id),
    onSuccess: (data: ErrorQuestion) => {
      qc.setQueryData(['errorQuestion', data.id], data)
      qc.invalidateQueries({ queryKey: ['errorQuestions'] })
    },
  })
}
