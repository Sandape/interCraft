"""Quality validation for generated research reports.

REQ-053 FR-018:
  (a) Not empty or template-only
  (b) >=1 specific company/product name
  (c) >=3 specific interview questions
  (d) >=1 ability dimension referenced (skip if new user with no ability data)

Returns (passed: bool, failures: list[str]).
"""
from __future__ import annotations

import re


def check_report_quality(
    report_md: str,
    *,
    company: str,
    user_has_ability_data: bool,
) -> tuple[bool, list[str]]:
    """Validate FR-018 quality criteria. Returns (passed, failure_reasons)."""
    failures: list[str] = []

    # (a) Not empty / template-only
    if not report_md or len(report_md.strip()) < 200:
        failures.append("report_too_short")
    if _is_template_only(report_md):
        failures.append("template_only")

    # (b) >=1 specific company or product name
    if not _mentions_company_or_product(report_md, company):
        failures.append("no_company_or_product_mentioned")

    # (c) >=3 specific interview questions
    question_count = _count_interview_questions(report_md)
    if question_count < 3:
        failures.append(f"insufficient_interview_questions (found {question_count}, need 3)")

    # (d) >=1 ability dimension reference (skip if new user)
    if user_has_ability_data:
        if not _mentions_ability_dimension(report_md):
            failures.append("no_ability_dimension_referenced")

    passed = len(failures) == 0
    return passed, failures


# --- helpers ---


_TEMPLATE_PATTERNS = re.compile(
    r"(暂无.*公开信息|无法获取|待补充|内容不足|placeholder)",
    re.IGNORECASE,
)

# Question patterns: numbered list items + ending with ? or full-width ？.
# DeepSeek Chinese reports almost always use ？; ASCII-only patterns caused
# every generated report to fail ``insufficient_interview_questions``.
_QUESTION_PATTERNS = [
    re.compile(r"^\s*[-*•]?\s*\d+[\.\)、]\s*.+[\?？]"),
    re.compile(r"^\s*[-*•]?\s*[一二三四五六七八九十][\.\)、]\s*.+[\?？]"),
    re.compile(r"^\s*[-*•]\s*.+[\?？]"),
    re.compile(r".+[？\?]\s*$"),
]


def _is_template_only(text: str) -> bool:
    """Detect placeholder / filler content."""
    if not text:
        return True
    # Heuristic: if the body is mostly short section headers without substance
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    non_heading_lines = [
        ln for ln in lines
        if not ln.startswith("#") and not ln.startswith("📋") and not ln.startswith("🏢")
        and not ln.startswith("📝") and not ln.startswith("🎯") and not ln.startswith("⚠️")
        and not ln.startswith("💡") and not ln.startswith("📊")
    ]
    if not non_heading_lines:
        return True
    if _TEMPLATE_PATTERNS.search(text):
        return True
    return False


def _count_interview_questions(text: str) -> int:
    """Count interview question markers — numbered / bulleted lines ending in ?/？."""
    count = 0
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for pat in _QUESTION_PATTERNS:
            if pat.match(line):
                count += 1
                break
    return count


def _mentions_company_or_product(text: str, company: str) -> bool:
    """Check whether the text mentions the company name or any concrete product."""
    if not company:
        return True  # can't verify, skip
    if company in text:
        return True
    # Look for typical Chinese product/service suffixes
    product_suffixes = [
        "APP", "app", "小程序", "平台", "系统", "框架", "服务", "组件", "数据库",
        "SDK", "sdk", "API", "api", "工具", "客户端", "后端", "前端",
    ]
    # Look for a word ending with one of these suffixes
    for suffix in product_suffixes:
        matches = re.findall(r"[一-鿿A-Za-z]{2,20}" + re.escape(suffix), text)
        if matches:
            return True
    return False


_ABILITY_KEYWORDS = [
    "技术深度", "架构设计", "工程实践", "沟通表达", "算法", "业务理解",
    "tech_depth", "architecture", "engineering_practice",
    "communication", "algorithm", "business",
]


def _mentions_ability_dimension(text: str) -> bool:
    for kw in _ABILITY_KEYWORDS:
        if kw in text:
            return True
    return False


__all__ = ["check_report_quality"]