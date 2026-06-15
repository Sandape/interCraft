/** Mutation hooks for tasks (US8). */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { Task } from '../../repositories/TaskRepository'
import { getTaskRepository } from '../../repositories/types'

export function useUpdateTaskStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      getTaskRepository().patch(id, { status }),
    onSuccess: (data: Task) => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}

export function useDeleteTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => getTaskRepository().delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}
