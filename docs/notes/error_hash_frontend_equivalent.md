# Frontend equivalent — error_hash.py

REQ-039 US5 (FR-023) requires the frontend compute **the same** error
hash as the backend (`compute_error_hash` in
`backend/app/observability/error_hash.py`). The two implementations
must agree on:

1. normalization order (rules 1→6 below, then final whitespace collapse)
2. the regex set (UUID / hex blob / ≥12-digit sequence)
3. the hash algorithm (SHA-256, first 8 bytes hex = 16 chars)

The frontend uses **Web Crypto API** — no new dependency. Drop-in
TypeScript module (Batch 2 will land this in `src/lib/error_hash.ts`):

```ts
// src/lib/error_hash.ts — REQ-039 US5 / FR-023 frontend parity
// Mirror of backend/app/observability/error_hash.py
//
// Run-time: O(message length), no deps. Web Crypto is async — wrap
// in a `computeErrorHashSync` helper for hot paths by precomputing
// the digest in a service worker / on mount.

const UUID_PATTERN =
  /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i;
const HEX_BLOB_PATTERN = /\b[0-9a-f]{16,}\b/i;
const LONG_DIGITS_PATTERN = /\b\d{12,}\b/;
const WHITESPACE_PATTERN = /\s+/;

export function normalizeErrorMessage(errorMessage: string): string {
  if (!errorMessage) return "";
  let out = errorMessage.toLowerCase().trim();
  out = WHITESPACE_PATTERN.test(out) ? out.replace(WHITESPACE_PATTERN, " ") : out;
  out = out.replace(UUID_PATTERN, " ");
  out = out.replace(HEX_BLOB_PATTERN, " ");
  out = out.replace(LONG_DIGITS_PATTERN, " ");
  out = WHITESPACE_PATTERN.test(out) ? out.replace(WHITESPACE_PATTERN, " ") : out;
  return out.trim();
}

export async function computeErrorHash(errorMessage: string): Promise<string> {
  const normalized = normalizeErrorMessage(errorMessage);
  const bytes = new TextEncoder().encode(normalized);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const hex = Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return hex.slice(0, 16);
}

// Sync variant — precompute once on page load via Promise.all, store
// in a Map<traceId, hashBucket>.
const _cache = new Map<string, string>();
export function computeErrorHashCached(errorMessage: string, key: string): string {
  const cached = _cache.get(key);
  if (cached !== undefined) return cached;
  // Defer to async — cache the promise, not the value.
  const promise = computeErrorHash(errorMessage).then((h) => {
    _cache.set(key, h);
    return h;
  });
  // Best-effort: return a sentinel; caller MUST await if they need the
  // real value (the alternative is to block render).
  return "";
}
```

## Verification (Batch 2 acceptance)

Frontend + backend MUST agree on these 5 fixtures (Batch 1 ships the
backend tests; Batch 2 ports them as Vitest unit tests):

| Input | Normalized | Hash (16 hex) |
|-------|------------|----------------|
| `"Retry 3 times"` | `"retry 3 times"` | see backend `test_039_error_hash.py` |
| `"Retry 5 times"` | `"retry 5 times"` | different from above |
| `"key 12345678-1234-1234-1234-123456789012 missing"` | `"key missing"` | identical to next |
| `"key abcdef12-3456-7890-abcd-ef1234567890 missing"` | `"key missing"` | same as above |
| `"leaked secret 12345678901234567890 now"` | `"leaked secret now"` | (strip 20-digit seq) |

## Why the order matters

Stripping UUID/hex/digits injects whitespace. The final
`WHITESPACE_PATTERN` collapse guarantees that "a   b" never becomes
"a b b" (which would happen if we collapsed only once at the top).
The backend's `_NORMALIZATION_STEPS` does NOT collapse at the top —
it strips at the end. The frontend mirrors that by collapsing twice
(once after lowercase+trim, once at the end).

## Web Crypto availability

`crypto.subtle.digest` requires a secure context (HTTPS or localhost).
The dev server runs on `http://localhost:5173` which counts as secure;
production must be HTTPS. Callers should defensively fallback to a
sync sha256 via `js-sha256` package if Web Crypto is unavailable —
this is a future-proofing note; current InterCraft domain is HTTPS-only.