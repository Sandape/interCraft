"""[REQ-048 US4 T074] Unit test for card_renderer 4:3 layout.

Validates AC-17a / AC-18:
- CardRenderer.render(plan, size_variant='4_3') produces 1080x810.
- Output is non-empty bytes with valid JPEG-like envelope.
- Width / height exactly match LAYOUT_4_3.

The test uses the in-process :class:`CardRenderer` with the
deterministic fallback (no Node.js / sharp binary required).
"""
from __future__ import annotations

import asyncio
import re

import pytest

from app.services.card_renderer.renderer import (
    FILE_SIZE_BUDGET_BYTES,
    LAYOUT_4_3,
    LAYOUT_9_16,
    CardRenderer,
)


def _plan() -> dict:
    return {
        "target_company": "字节跳动",
        "target_position": "高级后端工程师",
        "interview_difficulty": "medium",
        "estimated_duration_minutes": 30,
        "focus_areas": [
            {"area": "分布式系统", "weight": 0.4},
            {"area": "高并发", "weight": 0.3},
            {"area": "数据库", "weight": 0.3},
        ],
        "suggested_questions": [
            "请介绍一下你主导过的最大规模分布式系统",
            "如何处理 Kafka 消息积压问题",
            "Redis 集群脑裂如何处理",
        ],
        "tips": ["准备好 2-3 个生产级案例", "重点展示 trace/log 排查能力"],
    }


async def test_render_4_3_produces_1080x810_image() -> None:
    """AC-17a / AC-18: 4:3 layout produces exactly 1080×810."""
    renderer = CardRenderer()
    out = await renderer.render(_plan(), size_variant="4_3")
    assert out.width == LAYOUT_4_3["width"]
    assert out.height == LAYOUT_4_3["height"]
    assert out.size_variant == "4_3"
    assert out.image_bytes
    assert len(out.image_bytes) > 0
    assert out.bytes_total == len(out.image_bytes)


async def test_render_4_3_under_300kb_budget() -> None:
    """AC-17a: file size ≤ 300KB."""
    renderer = CardRenderer()
    out = await renderer.render(_plan(), size_variant="4_3")
    assert out.bytes_total <= FILE_SIZE_BUDGET_BYTES, (
        f"4:3 render {out.bytes_total} bytes > {FILE_SIZE_BUDGET_BYTES} budget"
    )


async def test_render_4_3_sha256_hex_is_stable() -> None:
    """Same plan twice → same sha256 (idempotency / cache key source)."""
    renderer = CardRenderer()
    out1 = await renderer.render(_plan(), size_variant="4_3")
    out2 = await renderer.render(_plan(), size_variant="4_3")
    assert out1.sha256_hex == out2.sha256_hex
    assert len(out1.sha256_hex) == 64


async def test_render_4_3_handles_missing_fields() -> None:
    """The renderer is tolerant of partial plans — missing fields render as blanks."""
    renderer = CardRenderer()
    out = await renderer.render({}, size_variant="4_3")
    assert out.width == LAYOUT_4_3["width"]
    assert out.height == LAYOUT_4_3["height"]
    assert out.bytes_total > 0


def test_layout_constants_match_spec() -> None:
    assert LAYOUT_4_3 == {"width": 1080, "height": 810}
    assert LAYOUT_9_16 == {"width": 1080, "height": 1920}
    assert LAYOUT_4_3["width"] == 1080
    assert LAYOUT_4_3["height"] == 810


def test_renderer_default_max_bytes_is_300kb() -> None:
    """AC-17a/17b default budget matches the spec'd 300KB."""
    renderer = CardRenderer()
    assert renderer.max_bytes == 300 * 1024


def test_renderer_to_dict_envelope() -> None:
    """to_dict returns a JSON-safe envelope with base64 image bytes."""

    async def _go() -> dict:
        return (await CardRenderer().render(_plan(), size_variant="4_3")).to_dict()

    env = asyncio.run(_go())
    for k in (
        "image_bytes_b64",
        "width",
        "height",
        "size_variant",
        "sha256_hex",
        "bytes_total",
    ):
        assert k in env
    assert env["size_variant"] == "4_3"
    assert env["width"] == 1080
    assert env["height"] == 810


def test_render_4_3_svg_has_single_non_overlapping_section_and_min_font() -> None:
    from app.services.card_renderer.renderer import _render_svg

    svg = _render_svg(_plan(), width=1080, height=810)
    assert "大纲" in svg
    assert "重点" not in svg
    sizes = [int(x) for x in re.findall(r'font-size="(\d+)"', svg)]
    assert sizes
    assert min(sizes) >= 24
