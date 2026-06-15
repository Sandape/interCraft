/**
 * Device fingerprint. Per FR / contracts/sessions.md, used to compute
 * `device_id = sha256(fingerprint)` and to detect "same device re-login".
 *
 * Web Crypto is preferred; `js-sha256` is the fallback for old browsers.
 */
import { sha256 } from 'js-sha256'

let cached: string | null = null

export function deviceFingerprint(): string {
  if (cached) return cached
  const parts = [
    typeof navigator !== 'undefined' ? navigator.userAgent : 'no-ua',
    typeof screen !== 'undefined' ? `${screen.width}x${screen.height}x${screen.colorDepth}` : 'no-screen',
    typeof Intl !== 'undefined' ? Intl.DateTimeFormat().resolvedOptions().timeZone : 'no-tz',
    typeof navigator !== 'undefined' ? navigator.language : 'no-lang',
  ]
  const joined = parts.join('|')
  let hex: string
  if (typeof crypto !== 'undefined' && crypto.subtle) {
    // Sync path — encode the bytes and hash with js-sha256 (still deterministic).
    // `crypto.subtle.digest` is async, so we use js-sha256 for the sync cache.
    hex = sha256(joined)
  } else {
    hex = sha256(joined)
  }
  cached = hex
  return hex
}

export function deviceName(): string {
  if (typeof navigator === 'undefined') return 'Unknown device'
  const ua = navigator.userAgent
  if (/Chrome\/(\d+)/.test(ua)) return `Chrome ${RegExp.$1}`
  if (/Firefox\/(\d+)/.test(ua)) return `Firefox ${RegExp.$1}`
  if (/Safari\/(\d+)/.test(ua) && /Version\/(\d+)/.test(ua)) return `Safari ${RegExp.$1}`
  if (/Edg\/(\d+)/.test(ua)) return `Edge ${RegExp.$1}`
  return 'Unknown device'
}

export function resetForTests(): void {
  cached = null
}
