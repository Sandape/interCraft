"""Markdown → plain text converter for WeChat delivery.

REQ-053 US4-AC5: convert Markdown to plain-text readable form with bounded
char count growth (≤10%).
"""
from __future__ import annotations

import re


# Conversion rules:
#   **bold**           -> 【bold】
#   ### heading        -> ▎heading
#   - / * list item    -> - list item (normalized)
#   ```code block```   -> [代码]\n<code content flattened>\n[/代码]
#   > blockquote       -> | <text>
_MARKDOWN_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_MARKDOWN_CODE_BLOCK = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_MARKDOWN_TABLE_ROW = re.compile(r"^\|.+\|$", re.MULTILINE)
_MARKDOWN_TABLE_SEP = re.compile(r"^\|[\s\-:|]+\|$", re.MULTILINE)
_LIST_ITEM = re.compile(r"^(\s*)([-*•]|\d+\.)\s+")
_MULTI_BLANK = re.compile(r"\n{3,}")
# Conversational openings LLMs often prepend to proactive push reports.
_FLUFF_OPENERS = re.compile(
    r"^(?:好的[，,]?\s*)?(?:这是为您生成的|以下是|为您整理了|已为您生成)"
    r"[^\n]{0,80}(?:报告|如下)[。.!！]?\s*",
    re.MULTILINE,
)

# Default WeChat pack size: prefer 1–2 long messages, not ~500-char spam.
# iLink/WeChat comfortably accepts multi-KB text; keep a hard ceiling.
DEFAULT_WECHAT_MAX_CHARS = 4000

# Chapter heading markers after convert_markdown_to_plain
_CHAPTER_BRIEFING = ("面试概览", "公司与产品速览")
_CHAPTER_PREP = ("面经汇总", "高频考察点", "薄弱环节", "最后建议", "历史对比")


def convert_markdown_to_plain(md: str) -> str:
    """Convert Markdown to plain text suitable for WeChat message segments."""
    if not md:
        return ""

    # 0. Strip conversational fluff (proactive push, not a chat reply)
    text = _FLUFF_OPENERS.sub("", md.lstrip()).lstrip()

    # 1. Code blocks first (so their content isn't mangled by other rules)
    def _replace_code_block(match: re.Match[str]) -> str:
        body = match.group(0)
        inner_lines = body.split("\n")
        inner = "\n".join(inner_lines[1:-1]) if len(inner_lines) >= 2 else ""
        return f"[代码]\n{inner.strip()}\n[/代码]"

    text = _MARKDOWN_CODE_BLOCK.sub(_replace_code_block, text)

    # 2. Tables: flatten to one-line per row (WeChat doesn't render tables)
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        if _MARKDOWN_TABLE_SEP.match(line):
            continue
        if _MARKDOWN_TABLE_ROW.match(line):
            cells = [c.strip() for c in line.strip("|").split("|")]
            out.append(" · ".join(cells))
        else:
            out.append(line)
    text = "\n".join(out)

    # 3. Headings → ▎ with surrounding blank lines for WeChat readability
    def _heading_repl(m: re.Match[str]) -> str:
        return f"\n▎{m.group(2).strip()}\n"

    text = _MARKDOWN_HEADING.sub(_heading_repl, text)

    # 4. Bold
    text = _MARKDOWN_BOLD.sub(lambda m: f"【{m.group(1)}】", text)

    # 5. Normalize list markers and collapse excess indentation
    normalized: list[str] = []
    for line in text.split("\n"):
        m = _LIST_ITEM.match(line)
        if m:
            indent = m.group(1)
            marker = m.group(2)
            body = line[m.end() :]
            depth = min(len(indent.replace("\t", "  ")) // 2, 1)
            prefix = "  " * depth
            if marker.endswith("."):
                normalized.append(f"{prefix}{marker} {body}")
            else:
                normalized.append(f"{prefix}- {body}")
        else:
            normalized.append(line.rstrip())
    text = "\n".join(normalized)

    # 6. Collapse 3+ blank lines; trim edges
    text = _MULTI_BLANK.sub("\n\n", text).strip()
    return text


def _split_chapters(text: str) -> list[str]:
    """Split plain text on ▎ chapter headings, keeping the marker on each part."""
    parts = re.split(r"(?=▎)", text)
    return [p.strip() for p in parts if p.strip()]


def _chapter_bucket(chapter: str) -> str:
    """Classify a chapter into briefing | prep | other."""
    head = chapter.split("\n", 1)[0]
    for key in _CHAPTER_BRIEFING:
        if key in head:
            return "briefing"
    for key in _CHAPTER_PREP:
        if key in head:
            return "prep"
    return "other"


def _hard_split_line(line: str, limit: int) -> list[str]:
    return [line[i : i + limit] for i in range(0, len(line), limit)]


def _pack_by_lines(text: str, body_limit: int) -> list[str]:
    """Fallback: pack by lines when a single logical pack exceeds the limit."""
    packed: list[str] = []
    current_lines: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current_lines, current_len
        if current_lines:
            packed.append("\n".join(current_lines).strip("\n"))
            current_lines = []
            current_len = 0

    for line in text.split("\n"):
        if line.startswith("▎") and current_lines and current_len > body_limit // 3:
            flush()
        line_len = len(line) + (1 if current_lines else 0)
        if len(line) > body_limit:
            flush()
            packed.extend(_hard_split_line(line, body_limit))
            continue
        if current_lines and current_len + line_len > body_limit:
            flush()
            line_len = len(line)
        current_lines.append(line)
        current_len += line_len
    flush()
    return [p for p in packed if p.strip()]


def segment_for_wechat(
    text: str,
    *,
    max_chars: int = DEFAULT_WECHAT_MAX_CHARS,
) -> list[str]:
    """Pack report plain text into 1–2 WeChat messages.

    Preferred layout (when chapters are present):
      (1/2) 面试概览 + 公司与产品速览
      (2/2) 面经汇总 + 高频考察点 + 薄弱环节 + 最后建议 (+ 历史对比)

    If the whole report fits in ``max_chars``, return a single message with no
    numbering. Only fall back to finer splits when a pack exceeds the limit.
    """
    if not text:
        return []

    prefix_budget = 8  # "(1/2)\n"
    body_limit = max(200, max_chars - prefix_budget)
    stripped = text.strip()

    # Short / no-chapter content: single message or line-pack fallback
    chapters = _split_chapters(stripped)
    has_markers = any(c.startswith("▎") for c in chapters)

    if not has_markers:
        if len(stripped) <= body_limit:
            return [stripped]
        return _annotate(_pack_by_lines(stripped, body_limit))

    briefing: list[str] = []
    prep: list[str] = []
    other: list[str] = []
    for ch in chapters:
        bucket = _chapter_bucket(ch)
        if bucket == "briefing":
            briefing.append(ch)
        elif bucket == "prep":
            prep.append(ch)
        else:
            other.append(ch)

    # Unclassified leading prose (rare) goes with briefing
    packs_raw: list[str] = []
    if other and not briefing and not prep:
        packs_raw.append("\n\n".join(other))
    else:
        head = "\n\n".join([*other, *briefing]).strip() if (other or briefing) else ""
        tail = "\n\n".join(prep).strip() if prep else ""
        if head and tail:
            packs_raw = [head, tail]
        elif head:
            packs_raw = [head]
        elif tail:
            packs_raw = [tail]

    # Prefer the 2-pack chapter layout whenever both buckets exist.
    # Only collapse to one message when a bucket is empty (or no chapters).
    joined = "\n\n".join(packs_raw)
    if len(packs_raw) == 1 and len(joined) <= body_limit:
        return [joined]
    if len(packs_raw) >= 2 and all(len(p) <= body_limit for p in packs_raw):
        return _annotate(packs_raw)
    if len(joined) <= body_limit:
        return [joined]

    # Expand oversized packs with line packing
    expanded: list[str] = []
    for pack in packs_raw:
        if len(pack) <= body_limit:
            expanded.append(pack)
        else:
            expanded.extend(_pack_by_lines(pack, body_limit))

    return _annotate(expanded)


def _annotate(segments: list[str]) -> list[str]:
    n = len(segments)
    if n <= 1:
        return segments
    return [f"({i + 1}/{n})\n{seg}" for i, seg in enumerate(segments)]


__all__ = [
    "DEFAULT_WECHAT_MAX_CHARS",
    "convert_markdown_to_plain",
    "segment_for_wechat",
]
