"""[REQ-048 US4 T077] Unit test for card file size budget.

Validates AC-17a + AC-17b:
- 4:3 (1080x810) render ≤ 300KB.
- 9:16 (1080x1920) with up to 8 outlines + 2 section titles ≤ 300KB.

The test exercises :class:`CardRenderer` directly with synthetic
InterviewPlan payloads matching the spec's worst-case outline counts.
"""
from __future__ import annotations

import asyncio

import pytest

from app.services.card_renderer.renderer import (
    FILE_SIZE_BUDGET_BYTES,
    CardRenderer,
)


def _worst_case_plan(*, max_outlines: int) -> dict:
    """Build a worst-case plan matching AC-17b's 7-8 outlines spec."""
    outlines = [
        f"Outline #{i + 1}: 分布式事务 / 微服务 / RAG / Kafka / Redis / JVM / MySQL 的实战细节与生产经验，考察候选人对技术栈的整体掌握深度与系统设计能力。"
        for i in range(max(1, max_outlines))
    ]
    return {
        "target_company": "字节跳动 (ByteDance)",
        "target_position": "高级后端工程师 — 分布式系统方向",
        "job_requirements": "具备 5 年以上 Java/Go 后端开发经验",
        "tech_stack": ["Java", "Go", "Kafka", "Redis"],
        "interview_difficulty": "hard",
        "estimated_duration_minutes": 45,
        "focus_areas": [
            {"area": "分布式系统设计", "weight": 0.30, "reason": "岗位核心"},
            {"area": "高并发架构", "weight": 0.25, "reason": "亿级 QPS"},
            {"area": "数据一致性", "weight": 0.20, "reason": "事务 / 锁 / 幂等"},
            {"area": "故障排查", "weight": 0.15, "reason": "生产稳定性"},
            {"area": "工程效能", "weight": 0.10, "reason": "CI/CD / 监控"},
        ],
        "suggested_questions": outlines,
        "tips": ["准备好 2-3 个亿级案例", "重点展示 trace/log 排查能力"],
        "web_research_summary": "字节跳动 2026 校招面试 3-5 轮",
    }


# ----- 4:3 -----


async def test_4_3_file_size_le_300kb() -> None:
    """AC-17a: 4:3 (1080×810) JPG ≤ 300KB."""
    renderer = CardRenderer()
    out = await renderer.render(_worst_case_plan(max_outlines=8), size_variant="4_3")
    assert out.bytes_total <= FILE_SIZE_BUDGET_BYTES, (
        f"4:3 {out.bytes_total} > {FILE_SIZE_BUDGET_BYTES} budget"
    )


async def test_4_3_budget_constant_is_300kb() -> None:
    """The FILE_SIZE_BUDGET_BYTES constant must be exactly 300 * 1024."""
    assert FILE_SIZE_BUDGET_BYTES == 300 * 1024


# ----- 9:16 -----


async def test_9_16_with_max_outlines_8_file_size_le_300kb() -> None:
    """AC-17b: 9:16 + 8 outlines + 2 section titles ≤ 300KB.

    This is the worst-case flagged in R5 — 9:16 pixels are 2.37x the
    4:3 count so the size budget is independently verified here.
    """
    renderer = CardRenderer()
    out = await renderer.render(_worst_case_plan(max_outlines=8), size_variant="9_16")
    assert out.bytes_total <= FILE_SIZE_BUDGET_BYTES, (
        f"9:16 + 8 outlines {out.bytes_total} > {FILE_SIZE_BUDGET_BYTES}"
    )


async def test_9_16_with_7_outlines_file_size_le_300kb() -> None:
    """AC-17b 7-outline scenario (lower bound of 7-8)."""
    renderer = CardRenderer()
    out = await renderer.render(_worst_case_plan(max_outlines=7), size_variant="9_16")
    assert out.bytes_total <= FILE_SIZE_BUDGET_BYTES


# ----- file size tests via the CLI script -----


def test_test_card_file_size_script_4_3_exits_0() -> None:
    """``python -m scripts.test_card_file_size --size 4_3`` exits 0."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "scripts.test_card_file_size", "--size", "4_3", "--json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    import json
    payload = json.loads(result.stdout)
    assert payload["size_variant"] == "4_3"
    assert payload["passed"] is True
    assert payload["bytes_total"] <= payload["budget_bytes"]


def test_test_card_file_size_script_9_16_max_8_exits_0() -> None:
    """``python -m scripts.test_card_file_size --size 9_16 --max-outlines 8`` exits 0."""
    import json
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.test_card_file_size",
            "--size",
            "9_16",
            "--max-outlines",
            "8",
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["size_variant"] == "9_16"
    assert payload["passed"] is True
    assert payload["width"] == 1080
    assert payload["height"] == 1920


# ----- pytest -k selectors for AC verification -----


async def test_4_3_size_variant_k_selector() -> None:
    """Pytest -k "4_3" selector works for AC-17a."""
    out = await CardRenderer().render(_worst_case_plan(max_outlines=8), size_variant="4_3")
    assert out.size_variant == "4_3"


async def test_9_16_size_variant_k_selector() -> None:
    """Pytest -k "9_16" selector works for AC-17b."""
    out = await CardRenderer().render(_worst_case_plan(max_outlines=8), size_variant="9_16")
    assert out.size_variant == "9_16"