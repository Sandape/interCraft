"""REQ-039 US5 — stable error hash for failure aggregation.

Implements the SHA256-prefix hash documented in spec.md §US5 + FR-021 /
FR-022 / FR-024, including the normalization rule set clarified on
2026-07-02 (Option B):

  1. lowercase
  2. strip leading / trailing whitespace
  3. collapse internal whitespace runs to a single space
  4. strip UUID-like tokens (8-4-4-4-12 hex)
  5. strip long hex blobs (>=16 hex digits)
  6. strip long digit sequences (>=12 consecutive digits)
  7. preserve ordinary numbers (1-11 digits) and all words

The frontend MUST compute the same hash via Web Crypto API
(`crypto.subtle.digest("SHA-256", ...)`) — see the companion spec
document ``docs/notes/error_hash_frontend_equivalent.md`` for the
exact TypeScript snippet.

Public API:

- :func:`compute_error_hash(error_message)` — returns 16-char hex
  prefix (8 bytes).
- :func:`normalize_error_message(error_message)` — exposed for tests
  + frontend parity verification.

Stability notes:

- The normalization is regex-based and order-sensitive (whitespace
  collapse runs AFTER strip; ID-strip runs on whitespace-collapsed
  text). The frontend MUST apply the rules in the SAME order to keep
  server / client buckets in sync.
- The hash is case-insensitive and ID-insensitive so that error text
  like ``"key abc12345-6789-... not found"`` and ``"key
  def67890-1234-... not found"`` collapse to one bucket while
  ``"retry 3 times"`` and ``"retry 5 times"`` remain distinct.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable

_UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_HEX_BLOB_PATTERN = re.compile(r"\b[0-9a-f]{16,}\b", re.IGNORECASE)
_LONG_DIGITS_PATTERN = re.compile(r"\b\d{12,}\b")
_WHITESPACE_PATTERN = re.compile(r"\s+")

# Used only for tests + introspection; the post-normalization step list
# is intentionally hard-coded (rules 4-6) instead of dynamically
# discovered, so the order is locked and the frontend can mirror it.
_NORMALIZATION_STEPS: tuple[Callable[[str], str], ...] = (
    lambda s: s.lower(),
    lambda s: s.strip(),
    lambda s: _WHITESPACE_PATTERN.sub(" ", s),
    lambda s: _UUID_PATTERN.sub(" ", s),
    lambda s: _HEX_BLOB_PATTERN.sub(" ", s),
    lambda s: _LONG_DIGITS_PATTERN.sub(" ", s),
)


def normalize_error_message(error_message: str) -> str:
    """Apply the 6 normalization rules in order (rules 1-3 + 4-6).

    Returns the normalized string. Subsequent re-collapsing of internal
    whitespace is required because each strip operation injects a
    single space; after all ID-like strips run we run one final
    whitespace collapse to keep the output stable.
    """
    if not error_message:
        return ""
    out = error_message
    for step in _NORMALIZATION_STEPS:
        out = step(out)
    # Final whitespace collapse: each strip rule injects a single space;
    # we don't want "abc def  ghi" — collapse back to "abc def ghi".
    out = _WHITESPACE_PATTERN.sub(" ", out).strip()
    return out


def compute_error_hash(error_message: str) -> str:
    """Return the first 8 bytes (16 hex chars) of SHA256 of the normalized message.

    The frontend MUST compute the same value via Web Crypto API on the
    same normalized text. The 8-byte prefix gives a 64-bit collision
    space, which is sufficient for bucketing (collision probability
    ~1/1.8e19 at 10M items — well under any realistic log center
    cardinality).
    """
    normalized = normalize_error_message(error_message)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest[:16]


__all__ = ["compute_error_hash", "normalize_error_message"]