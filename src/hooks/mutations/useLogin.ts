/**
 * useLogin — POST /auth/login mutation.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deviceFingerprint, deviceName } from '../../api/device-fingerprint'
import { AuthError } from '../../api/errors'
import type { AuthLoginResponse } from '../../api/types'
import { type LoginInput } from '../../repositories/AuthRepository'
import { getAuthRepository } from '../../repositories/types'
import { setTokens, clearTokens } from '../../api/token-storage'
import { useAuthStore } from '../../stores/useAuthStore'
import { CURRENT_USER_KEY } from '../queries/useCurrentUser'

export function useLogin() {
  const qc = useQueryClient()
  const setUser = useAuthStore((s) => s.setUser)
  return useMutation<AuthLoginResponse, AuthError, Omit<LoginInput, 'device_fingerprint' | 'device_name'>>({
    mutationFn: (input) =>
      getAuthRepository().login({
        ...input,
        device_fingerprint: deviceFingerprint(),
        device_name: deviceName(),
      }),
    onSuccess: (data) => {
      setTokens(data.tokens)
      setUser(data.user)
      void qc.invalidateQueries({ queryKey: CURRENT_USER_KEY })
    },
    onError: () => {
      clearTokens()
    },
  })
}
