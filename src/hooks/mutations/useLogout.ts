/**
 * useLogout — POST /auth/logout + clear local state.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { clearTokens } from '../../api/token-storage'
import { getAuthRepository } from '../../repositories/types'
import { useAuthStore } from '../../stores/useAuthStore'

export function useLogout() {
  const qc = useQueryClient()
  const clear = useAuthStore((s) => s.clear)
  return useMutation<void, Error, void>({
    mutationFn: async () => {
      try {
        await getAuthRepository().logout()
      } finally {
        clearTokens()
        clear()
        qc.clear()
      }
    },
  })
}
