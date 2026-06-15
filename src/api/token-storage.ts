/**
 * Token storage — in-memory mirror of sessionStorage.
 *
 * Tokens are NEVER stored in Zustand or React state directly, so that
 * a single 401 + page reload cannot leak them. sessionStorage survives
 * reloads but is per-tab (good — refresh tokens are per-device).
 */
import { env } from './env'

const ACCESS_KEY = 'ic.access_token'
const REFRESH_KEY = 'ic.refresh_token'

interface MemoryStore {
  access: string | null
  refresh: string | null
}

const memory: MemoryStore = { access: null, refresh: null }

function readSession(key: string): string | null {
  if (typeof sessionStorage === 'undefined') return null
  try {
    return sessionStorage.getItem(key)
  } catch {
    return null
  }
}

function writeSession(key: string, value: string | null): void {
  if (typeof sessionStorage === 'undefined') return
  try {
    if (value === null) sessionStorage.removeItem(key)
    else sessionStorage.setItem(key, value)
  } catch {
    /* quota or private mode — ignore */
  }
}

export function setTokens(tokens: { access_token: string; refresh_token: string }): void {
  memory.access = tokens.access_token
  memory.refresh = tokens.refresh_token
  writeSession(ACCESS_KEY, tokens.access_token)
  writeSession(REFRESH_KEY, tokens.refresh_token)
}

export function getAccessToken(): string | null {
  if (memory.access) return memory.access
  // In mock mode the repositories do not call apiClient, so we never
  // need to fabricate a token. Returning null here makes `hasTokens()`
  // honest, which is what AuthGuard relies on.
  if (env.USE_MOCK) return null
  const v = readSession(ACCESS_KEY)
  memory.access = v
  return v
}

export function getRefreshToken(): string | null {
  if (memory.refresh) return memory.refresh
  if (env.USE_MOCK) return null
  const v = readSession(REFRESH_KEY)
  memory.refresh = v
  return v
}

export function clearTokens(): void {
  memory.access = null
  memory.refresh = null
  writeSession(ACCESS_KEY, null)
  writeSession(REFRESH_KEY, null)
}

export function hasTokens(): boolean {
  return getAccessToken() !== null
}
