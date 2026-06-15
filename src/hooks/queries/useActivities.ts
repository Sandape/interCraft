/** React Query hook for activities cursor-paginated feed (US8). */
import { useQuery } from '@tanstack/react-query'
import type { ActivityList } from '../../repositories/ActivityRepository'
import { getActivityRepository } from '../../repositories/types'

export function useActivities(cursor?: string, limit?: number) {
  return useQuery<ActivityList>({
    queryKey: ['activities', cursor, limit],
    queryFn: () => getActivityRepository().list({ cursor, limit }),
    staleTime: 15_000,
  })
}
