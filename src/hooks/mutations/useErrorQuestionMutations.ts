/** Mutation hooks for error questions (US6). */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { ErrorQuestion } from '../../repositories/ErrorQuestionRepository'
import { getErrorQuestionRepository } from '../../repositories/types'

type ErrorQuestionList = {
  data: ErrorQuestion[]
  next_cursor: string | null
  has_more: boolean
}

function replaceCachedQuestion(old: ErrorQuestionList | undefined, next: ErrorQuestion) {
  if (!old) return old
  return {
    ...old,
    data: old.data.map((item) => (item.id === next.id ? next : item)),
  }
}

function removeCachedQuestion(old: ErrorQuestionList | undefined, id: string) {
  if (!old) return old
  return {
    ...old,
    data: old.data.filter((item) => item.id !== id),
  }
}

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
      qc.setQueriesData<ErrorQuestionList>({ queryKey: ['errorQuestions'] }, (old) => replaceCachedQuestion(old, data))
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
      qc.setQueriesData<ErrorQuestionList>({ queryKey: ['errorQuestions'] }, (old) => removeCachedQuestion(old, id))
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
      qc.setQueriesData<ErrorQuestionList>({ queryKey: ['errorQuestions'] }, (old) => replaceCachedQuestion(old, data))
      qc.invalidateQueries({ queryKey: ['errorQuestions'] })
    },
  })
}

export function useRecallErrorQuestion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => getErrorQuestionRepository().recall(id),
    onSuccess: (data: ErrorQuestion) => {
      qc.setQueryData(['errorQuestion', data.id], data)
      qc.setQueriesData<ErrorQuestionList>({ queryKey: ['errorQuestions'] }, (old) => replaceCachedQuestion(old, data))
      qc.invalidateQueries({ queryKey: ['errorQuestions'] })
    },
  })
}
