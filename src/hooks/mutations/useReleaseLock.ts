/** React Query mutation wrapper for lock release. */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { LockRepository, type ReleaseResponse } from '../../repositories/LockRepository'

export function useReleaseLock() {
  const queryClient = useQueryClient()

  return useMutation<ReleaseResponse, Error, string>({
    mutationFn: (lockId: string) => LockRepository.release(lockId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lockStatus'] })
    },
  })
}
