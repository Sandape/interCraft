/** Cursor-based pagination helpers — DEC-P2-1.
 *
 * Encodes/decodes opaque base64url JSON cursors for use with the activities
 * and jobs list endpoints. Matches backend `app/domain/pagination.py`.
 */

export interface CursorPayload {
  ts: string // ISO 8601
  id: string // uuid v7
}

export function encodeCursor(payload: CursorPayload): string {
  const json = JSON.stringify(payload)
  // Browser-compatible base64url encoding
  const base64 = btoa(unescape(encodeURIComponent(json)))
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

export function decodeCursor(opaque: string): CursorPayload {
  // Normalize base64url → base64
  let base64 = opaque.replace(/-/g, '+').replace(/_/g, '/')
  while (base64.length % 4) base64 += '='
  const json = decodeURIComponent(escape(atob(base64)))
  return JSON.parse(json) as CursorPayload
}
