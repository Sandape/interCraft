/// <reference types="vite/client" />

/**
 * Typed environment access for the frontend.
 *
 * - VITE_USE_MOCK=true  → all repositories return mock data (no network).
 * - VITE_API_BASE_URL   → base URL of the FastAPI backend.
 * - VITE_WS_URL         → optional WebSocket base (used in Phase 2+).
 *
 * Values come from Vite's `import.meta.env` (loaded from `.env.local`).
 */

export interface Env {
  USE_MOCK: boolean
  API_BASE_URL: string
  WS_URL: string
}

function readBool(name: string, fallback: boolean): boolean {
  const raw = (import.meta.env as Record<string, string | undefined>)[name]
  if (raw === undefined) return fallback
  return ['1', 'true', 'yes', 'on'].includes(raw.toLowerCase())
}

function readStr(name: string, fallback: string): string {
  const raw = (import.meta.env as Record<string, string | undefined>)[name]
  return raw && raw.length > 0 ? raw : fallback
}

export const env: Env = {
  USE_MOCK: readBool('VITE_USE_MOCK', true),
  // Default to relative URL so requests go to the Vite dev server, which
  // proxies /api and /openapi.json to the FastAPI backend (see vite.config.ts).
  // This avoids the Windows "localhost resolves to ::1 first" pitfall and
  // removes the need for CORS in dev. Override in `.env.local` for staging
  // (e.g. https://api.staging.example.com) or set to a full URL in prod.
  API_BASE_URL: readStr('VITE_API_BASE_URL', ''),
  WS_URL: readStr('VITE_WS_URL', ''),
}

export function newRequestId(): string {
  // RFC 4122 v4 — sufficient for request correlation
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}
