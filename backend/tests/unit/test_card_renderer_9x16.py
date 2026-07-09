"""[REQ-048 US4 T075] Unit test for card_renderer 9:16 layout.

Validates AC-17b / AC-18:
- CardRenderer.render(plan, size_variant='9_16') produces 1080x1920.
- 7-8 outlines + 2 section titles (大纲 + 关注重点) scenario stays
  under 300KB.
- Width / height exactly match LAYOUT_9_16.
"""
from __future__ import annotations

import asyncio

import pytest

from app.services.card_renderer.renderer import (
    FILE_SIZE_BUDGET_BYTES,
    LAYOUT_9_16,
    CardRenderer,
)


def _plan_9_16(max_outlines: int = 8) -> dict:
    return {
        "target_company": "字节跳动 (ByteDance)",
        "target_position": "高级后端工程师 — 分布式系统",
        "interview_difficulty": "hard",
        "estimated_duration_minutes": 45,
        "focus_areas": [
            {"area": "分布式系统设计", "weight": 0.30, "reason": "岗位核心"},
            {"area": "高并发架构", "weight": 0.25, "reason": "亿级 QPS"},
            {"area": "数据一致性", "weight": 0.20, "reason": "事务 / 锁 / 幂等"},
            {"area": "故障排查", "weight": 0.15, "reason": "生产稳定性"},
            {"area": "工程效能", "weight": 0.10, "reason": "CI/CD / 监控"},
        ],
        "suggested_questions": [
            f"Outline #{i + 1}: 分布式事务 / 微服务 / RAG / Kafka / Redis / JVM / MySQL 的实战细节与生产经验，考察候选人对技术栈的整体掌握深度与系统设计能力。"
            for i in range(max_outlines)
        ],
        "tips": [
            "准备好 2-3 个你主导过的亿级 QPS 系统设计案例",
            "重点展示你对 Kafka exactly-once 语义 + Redis 集群脑裂 + 分布式事务的真实理解",
        ],
    }


async def test_render_9_16_produces_1080x1920_image() -> None:
    """AC-17b / AC-18: 9:16 layout produces exactly 1080×1920."""
    renderer = CardRenderer()
    out = await renderer.render(_plan_9_16(), size_variant="9_16")
    assert out.width == LAYOUT_9_16["width"]
    assert out.height == LAYOUT_9_16["height"]
    assert out.size_variant == "9_16"


async def test_render_9_16_with_max_outlines_8_with_section_titles() -> None:
    """AC-17b worst case: 7-8 outlines + 2 section titles stays ≤300KB.

    The 9:16 layout includes 2 section titles (大纲 + 关注重点)
    splitting the vertical column. This is the scenario flagged in
    R5 — 9:16 pixels ≈ 4:3 * 2.37x and we MUST independently verify
    the file-size budget for the worst-case outline count.
    """
    renderer = CardRenderer()
    out = await renderer.render(_plan_9_16(max_outlines=8), size_variant="9_16")
    assert out.bytes_total <= FILE_SIZE_BUDGET_BYTES, (
        f"9:16 + 8 outlines render {out.bytes_total} bytes > {FILE_SIZE_BUDGET_BYTES}"
    )


async def test_render_9_16_with_7_outlines_under_budget() -> None:
    """AC-17b 7-outline scenario (lower bound of 7-8)."""
    renderer = CardRenderer()
    out = await renderer.render(_plan_9_16(max_outlines=7), size_variant="9_16")
    assert out.bytes_total <= FILE_SIZE_BUDGET_BYTES


async def test_render_9_16_sha256_hex_format() -> None:
    out = await CardRenderer().render(_plan_9_16(), size_variant="9_16")
    assert len(out.sha256_hex) == 64
    assert all(c in "0123456789abcdef" for c in out.sha256_hex)


async def test_render_9_16_layout_constants() -> None:
    """LAYOUT_9_16 constants match FR-052 spec."""
    assert LAYOUT_9_16["width"] == 1080
    assert LAYOUT_9_16["height"] == 1920


async def test_render_9_16_section_titles_emitted() -> None:
    """The 9:16 SVG body must include 2 section titles (大纲 + 关注重点)."""
    from app.services.card_renderer.renderer import (
        _focus_area_lines,
        _render_svg,
        size_is_9_16,
    )

    assert size_is_9_16(1080, 1920) is True
    assert size_is_9_16(1080, 810) is False
    plan = _plan_9_16(max_outlines=8)
    svg = _render_svg(plan, width=1080, height=1920)
    assert "大纲" in svg
    assert "关注重点" in svg
    # _focus_area_lines helper is exercised by the renderer.
    lines = _focus_area_lines(plan["focus_areas"])
    assert len(lines) == 5
    assert any("分布式系统设计" in ln for ln in lines)


def test_size_is_9_16_helper() -> None:
    from app.services.card_renderer.renderer import size_is_9_16

    assert size_is_9_16(1080, 1920) is True
    assert size_is_9_16(1080, 810) is False
    assert size_is_9_16(720, 1280) is False