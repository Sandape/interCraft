/**
 * useRegister — POST /auth/register mutation.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deviceFingerprint, deviceName } from '../../api/device-fingerprint'
import { AuthError } from '../../api/errors'
import type { AuthRegisterResponse } from '../../api/types'
import { type RegisterInput } from '../../repositories/AuthRepository'
import { getAuthRepository } from '../../repositories/authRepositories'
import { setTokens } from '../../api/token-storage'
import { useAuthStore } from '../../stores/useAuthStore'
import { CURRENT_USER_KEY } from '../queries/useCurrentUser'
import {
  clearOnboardingState,
  onboardingStorageKey,
} from '../../features/onboarding/onboarding-state'

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
      // A browser can be shared by multiple local accounts. A newly registered
      // user must never inherit another account's completed onboarding draft.
      clearOnboardingState()
      clearOnboardingState(undefined, onboardingStorageKey(data.user.id))
      setTokens(data.tokens)
      setUser(data.user)
      void qc.invalidateQueries({ queryKey: CURRENT_USER_KEY })
    },
  })
}
