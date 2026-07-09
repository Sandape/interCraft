"""[REQ-048 US4 T079] Integration test for card render end-to-end.

Validates AC-17a / AC-17b / AC-22:
- InterviewPlan → image bytes through the full CardRenderer pipeline.
- File size ≤ 300KB for both 4:3 and 9:16 variants.
- The renderer is callable from an async context (no blocking sync I/O).
"""
from __future__ import annotations

import io

import pytest
from PIL import Image

from app.services.card_renderer.renderer import (
    FILE_SIZE_BUDGET_BYTES,
    LAYOUT_4_3,
    LAYOUT_9_16,
    CardRenderer,
)


pytestmark = pytest.mark.integration


def _assert_valid_jpeg(image_bytes: bytes, *, width: int, height: int) -> None:
    image = Image.open(io.BytesIO(image_bytes))
    assert image.format == "JPEG"
    assert image.size == (width, height)
    image.verify()


def _plan() -> dict:
    return {
        "target_company": "字节跳动",
        "target_position": "高级后端工程师",
        "interview_difficulty": "medium",
        "estimated_duration_minutes": 30,
        "focus_areas": [
            {"area": "分布式系统", "weight": 0.4, "reason": "岗位核心"},
            {"area": "高并发", "weight": 0.3, "reason": "亿级 QPS"},
            {"area": "数据库", "weight": 0.3, "reason": "事务 / 锁"},
        ],
        "suggested_questions": [
            "请介绍一下你主导过的最大规模分布式系统",
            "如何处理 Kafka 消息积压问题",
            "Redis 集群脑裂如何处理",
            "分布式事务如何选型",
            "请描述一个生产事故的根因分析过程",
        ],
        "tips": ["准备好 2-3 个生产级案例", "重点展示 trace/log 排查能力"],
    }


async def test_card_render_e2e_4_3() -> None:
    """AC-17a / AC-22: end-to-end 4:3 render under 300KB."""
    renderer = CardRenderer()
    out = await renderer.render(_plan(), size_variant="4_3")
    assert out.image_bytes
    assert len(out.image_bytes) <= FILE_SIZE_BUDGET_BYTES
    assert out.width == LAYOUT_4_3["width"]
    assert out.height == LAYOUT_4_3["height"]
    _assert_valid_jpeg(
        out.image_bytes,
        width=LAYOUT_4_3["width"],
        height=LAYOUT_4_3["height"],
    )


async def test_card_render_e2e_9_16() -> None:
    """AC-17b / AC-22: end-to-end 9:16 render under 300KB."""
    renderer = CardRenderer()
    out = await renderer.render(_plan(), size_variant="9_16")
    assert out.image_bytes
    assert len(out.image_bytes) <= FILE_SIZE_BUDGET_BYTES
    assert out.width == LAYOUT_9_16["width"]
    assert out.height == LAYOUT_9_16["height"]
    _assert_valid_jpeg(
        out.image_bytes,
        width=LAYOUT_9_16["width"],
        height=LAYOUT_9_16["height"],
    )


async def test_card_render_e2e_to_dict_envelope() -> None:
    """AC-22: response envelope is JSON-safe."""
    renderer = CardRenderer()
    out = await renderer.render(_plan(), size_variant="4_3")
    env = out.to_dict()
    assert env["size_variant"] == "4_3"
    assert env["width"] == 1080
    assert env["height"] == 810
    assert env["bytes_total"] == len(out.image_bytes)
    assert env["sha256_hex"] == out.sha256_hex
    assert env["image_bytes_b64"]  # base64 string present


async def test_card_render_e2e_idempotency() -> None:
    """Same plan → same sha256 (cache key source for AC-22 / AC-24)."""
    renderer = CardRenderer()
    a = await renderer.render(_plan(), size_variant="4_3")
    b = await renderer.render(_plan(), size_variant="4_3")
    assert a.sha256_hex == b.sha256_hex
