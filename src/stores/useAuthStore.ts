/**
 * useAuthStore — user object + auth status.
 *
 * **Tokens never live here** — they are managed by `src/api/token-storage.ts`
 * and attached per-request by the fetch client. This separation prevents
 * tokens from leaking via React DevTools, persisted state, or Zustand
 * subscriptions.
 */
import { create } from 'zustand'
import type { PublicUser } from '../api/types'

export type AuthStatus = 'unknown' | 'authenticated' | 'unauthenticated'

interface AuthState {
  user: PublicUser | null
  status: AuthStatus
  setUser: (user: PublicUser | null) => void
  clear: () => void
  setStatus: (s: AuthStatus) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  status: 'unknown',
  setUser: (user) =>
    set(() => ({
      user,
      status: user ? 'authenticated' : 'unauthenticated',
    })),
  clear: () => set({ user: null, status: 'unauthenticated' }),
  setStatus: (status) => set({ status }),
}))
