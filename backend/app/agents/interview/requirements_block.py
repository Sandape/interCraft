"""019 — build_requirements_block: turn jobs.requirements_md into a prompt
section that fits the 1500-token budget. Returns enough metadata for the
graph to log the truncation decision.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

MAX_REQUIREMENTS_TOKENS = 1500

_BLOCK_HEADER = "## 岗位招聘需求"
_BLOCK_HEADER_TRUNCATED = "## 岗位招聘需求(已截断到前 {n} token)"


def _count_tokens(text: str) -> list[int]:
    """Encode text to tokens. Tries tiktoken first; falls back to a
    conservative char-based estimate (≈ 1 token / 1.5 chars for CJK + ASCII
    mixed) when the package isn't installed. Returns a single-element list
    (the token ids) for compatibility with the tiktoken path; the estimate
    path returns an empty list and the caller uses ``estimate_tokens``.
    """
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.encoding_for_model("gpt-4")
        return enc.encode(text)
    except Exception:
        return []


def _decode_tokens(tokens: list[int]) -> str | None:
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.encoding_for_model("gpt-4")
        return enc.decode(tokens)
    except Exception:
        return None


def estimate_tokens(text: str) -> int:
    """Rough CJK-friendly token count when tiktoken isn't available."""
    if not text:
        return 0
    # 1 CJK char ≈ 1.5 token; 1 ASCII char ≈ 0.25 token
    cjk = sum(1 for c in text if ord(c) > 0x2E80)
    ascii_ = len(text) - cjk
    return int(cjk * 1.5 + ascii_ * 0.25)


def build_requirements_block(
    requirements_md: str | None,
    *,
    max_tokens: int = MAX_REQUIREMENTS_TOKENS,
) -> tuple[str, bool, bool, int]:
    """Build the prompt section for the requirements injection.

    Returns ``(block_text, requirements_provided, requirements_truncated, original_chars)``.
    """
    if not requirements_md or not requirements_md.strip():
        return "", False, False, 0

    original_chars = len(requirements_md)
    tokens = _count_tokens(requirements_md)
    if tokens:
        token_count = len(tokens)
    else:
        token_count = estimate_tokens(requirements_md)

    if token_count <= max_tokens:
        return (
            f"{_BLOCK_HEADER}\n{requirements_md}",
            True,
            False,
            original_chars,
        )

    if tokens:
        truncated = tokens[:max_tokens]
        truncated_text = _decode_tokens(truncated) or requirements_md[:max_tokens * 2]
    else:
        # approximate char truncation when tiktoken is missing
        truncated_text = requirements_md[: max_tokens * 2]

    block = (
        _BLOCK_HEADER_TRUNCATED.format(n=max_tokens)
        + "\n"
        + truncated_text
    )
    logger.info(
        "requirements_md_truncated",
        original_chars=original_chars,
        truncated_to_tokens=max_tokens,
        ratio=round(token_count / max_tokens, 2) if max_tokens else 1.0,
    )
    return block, True, True, original_chars


__all__ = [
    "MAX_REQUIREMENTS_TOKENS",
    "build_requirements_block",
    "estimate_tokens",
]
