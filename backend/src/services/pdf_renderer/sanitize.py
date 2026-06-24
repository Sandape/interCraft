"""HTML sanitizer for the PDF renderer.

Defense-in-depth: frontend `sanitizeHtml()` already strips dangerous tags
before POST; this module is the backend second layer. Runs BEFORE
`render_with_playwright()` so even a malicious direct API caller cannot
inject script/iframe/on* payloads into the Playwright page.

Ported from `src/lib/resume-renderer/index.ts:sanitizeHtml` — same regex
strategy so frontend and backend filtering stay in sync.

Contract: specs/027-resume-center-muji-alignment/contracts/pdf-export.md
"""
from __future__ import annotations

import re

# Tag-stripping patterns — remove the tag AND its content for paired tags
# (script/iframe/object can carry executable payload in their text body),
# and just the tag for void <embed>.
_SCRIPT_RE = re.compile(
    r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>",
    re.IGNORECASE | re.DOTALL,
)
_IFRAME_RE = re.compile(
    r"<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>",
    re.IGNORECASE | re.DOTALL,
)
_OBJECT_RE = re.compile(
    r"<object\b[^<]*(?:(?!<\/object>)<[^<]*)*<\/object>",
    re.IGNORECASE | re.DOTALL,
)
_EMBED_RE = re.compile(r"<embed\b[^>]*>", re.IGNORECASE)

# on* event handler attributes — covers double-quoted, single-quoted, and
# unquoted attribute values.
_ON_ATTR_DQ_RE = re.compile(r'\son\w+\s*=\s*"[^"]*"', re.IGNORECASE)
_ON_ATTR_SQ_RE = re.compile(r"\son\w+\s*=\s*'[^']*'", re.IGNORECASE)
_ON_ATTR_UQ_RE = re.compile(r"\son\w+\s*=\s*[^\s>]+", re.IGNORECASE)

# `javascript:` protocol (in href/src/etc) — strip the protocol so the URL
# becomes a no-op relative link.
_JS_PROTOCOL_RE = re.compile(r"javascript:", re.IGNORECASE)


def sanitize_html(html: str) -> str:
    """Strip XSS vectors from an HTML string.

    Removes:
    - ``<script>`` / ``<iframe>`` / ``<object>`` tags AND their text content
    - ``<embed>`` void tags
    - ``on*`` event handler attributes (onclick, onload, onerror, ...)
    - ``javascript:`` protocol URIs

    Safe content (paragraphs, spans, styles, images, links with http(s)) is
    preserved verbatim. Returns the cleaned HTML string.

    Pure function: same input → same output, no side effects.
    """
    if not html:
        return ""
    cleaned = _SCRIPT_RE.sub("", html)
    cleaned = _IFRAME_RE.sub("", cleaned)
    cleaned = _OBJECT_RE.sub("", cleaned)
    cleaned = _EMBED_RE.sub("", cleaned)
    cleaned = _ON_ATTR_DQ_RE.sub("", cleaned)
    cleaned = _ON_ATTR_SQ_RE.sub("", cleaned)
    cleaned = _ON_ATTR_UQ_RE.sub("", cleaned)
    cleaned = _JS_PROTOCOL_RE.sub("", cleaned)
    return cleaned
