/**
 * useRegister — POST /auth/register mutation.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deviceFingerprint, deviceName } from '../../api/device-fingerprint'
import { AuthError } from '../../api/errors'
import type { AuthRegisterResponse } from '../../api/types'
import { type RegisterInput } from '../../repositories/AuthRepository'
import { getAuthRepository } from '../../repositories/types'
import { setTokens } from '../../api/token-storage'
import { useAuthStore } from '../../stores/useAuthStore'
import { CURRENT_USER_KEY } from '../queries/useCurrentUser'

export function useRegister() {
  const qc = useQueryClient()
  const setUser = useAuthStore((s) => s.setUser)
  return useMutation<
    AuthRegisterResponse,
    AuthError,
    Omit<RegisterInput, 'device_fingerprint' | 'device_name'>
  >({
    mutationFn: (input) =>
      getAuthRepository().register({
        ...input,
        device_fingerprint: deviceFingerprint(),
        device_name: deviceName(),
      }),
    onSuccess: (data) => {
      setTokens(data.tokens)
      setUser(data.user)
      void qc.invalidateQueries({ queryKey: CURRENT_USER_KEY })
    },
  })
}
