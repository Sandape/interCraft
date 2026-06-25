"""PII redactor for semantic memories.

Spec FR-009: "Memory extraction MUST redact PII before storage; facts
containing PII beyond the necessary are blocked."

US1 scope: regex-based redaction for the two most common PII patterns —
email addresses and phone numbers (CN + US formats). The redactor returns
a tuple of (redacted_value, blocked) where `blocked=True` means the value
was so PII-heavy that it should not be stored at all.

Design choice: redaction (replace with `[REDACTED]`) for incidental PII
(e.g., "contact me at foo@bar.com for details" → "contact me at [REDACTED]
for details"). Blocking is reserved for values that are entirely PII
(e.g., a fact_value that is just "foo@bar.com"). This matches the spec's
"redact before storage" + "block beyond the necessary" semantics.

Future: LLM-based PII classifier (deferred — US4 will scope this).
"""
from __future__ import annotations

import re

# Email: standard RFC 5322 simplified pattern.
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# CN mobile: 11 digits starting with 1, optional +86 prefix.
# US phone: (xxx) xxx-xxxx or xxx-xxx-xxxx or xxxxxxxxxx with 10 digits
# (lenient — context-free phone detection is hard; we err on the side of
# matching 10+ digit runs prefixed by optional +).
_PHONE_RE = re.compile(
    r"(?:\+?86[-\s]?)?1[3-9]\d{9}"  # CN mobile
    r"|\+?1[-\s]?\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}"  # US
)

_REDACTED = "[REDACTED]"


def redact(value: str) -> tuple[str, bool]:
    """Redact PII from `value`.

    Returns
    -------
    tuple of (redacted_value, blocked)
        - redacted_value: PII replaced with `[REDACTED]`
        - blocked: True if the value is so PII-heavy it should not be stored.

    Blocking heuristic: block only when the entire value was PII (i.e.,
    after redaction the value is empty or only the placeholder remains).
    We deliberately do NOT block short Chinese values like "前端" or
    "字节" — they are legitimate fact values, not PII leakage.

    Examples:
      - "foo@bar.com" → ("[REDACTED]", True)  # entire value is PII
      - "前端开发 联系 foo@bar.com" → ("前端开发 联系 [REDACTED]", False)
      - "前端" → ("前端", False)  # short but legit
      - "13800138000" → ("[REDACTED]", True)  # entire value is PII
    """
    if not value:
        return value, False

    redacted = _EMAIL_RE.sub(_REDACTED, value)
    redacted = _PHONE_RE.sub(_REDACTED, redacted)

    # Block only if the value was essentially only PII — i.e., after
    # redaction nothing meaningful remains. The placeholder itself is
    # not meaningful.
    stripped = redacted.replace(_REDACTED, "").strip()
    if not stripped:
        return redacted, True

    return redacted, False


__all__ = ["redact"]
