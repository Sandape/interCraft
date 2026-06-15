/** React Query mutation wrapper for lock acquire. */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { LockRepository, type AcquireInput, type LockStatus } from '../../repositories/LockRepository'

export function useAcquireLock() {
  const queryClient = useQueryClient()

  return useMutation<LockStatus, Error, AcquireInput>({
    mutationFn: (input: AcquireInput) => LockRepository.acquire(input),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['lockStatus', variables.resource_type, variables.resource_id],
      })
    },
  })
}
