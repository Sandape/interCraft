/** React Query hooks for tasks (US8). */
import { useQuery } from '@tanstack/react-query'
import type { Task } from '../../repositories/TaskRepository'
import { getTaskRepository } from '../../repositories/types'

export function useTasks(params?: { status?: string; limit?: number }) {
  return useQuery<{ data: Task[] }>({
    queryKey: ['tasks', params],
    queryFn: () => getTaskRepository().list(params),
    staleTime: 30_000,
  })
}
