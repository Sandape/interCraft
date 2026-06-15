/** React Query query wrapper for lock status. */
import { useQuery } from '@tanstack/react-query'
import { LockRepository, type LockStatus } from '../../repositories/LockRepository'

export function useLockStatus(resourceType: string, resourceId: string | null) {
  return useQuery<LockStatus>({
    queryKey: ['lockStatus', resourceType, resourceId],
    queryFn: () => LockRepository.getStatus(resourceType, resourceId!),
    enabled: !!resourceId,
    refetchInterval: 30_000, // Poll every 30s as WS fallback
  })
}
