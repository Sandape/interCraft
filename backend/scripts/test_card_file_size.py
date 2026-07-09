"""[REQ-048 AC-17a / AC-17b] Card file-size budget assertion script.

Renders a synthetic InterviewPlan at the requested size_variant and
asserts the resulting JPG envelope is within the 300KB budget
(SC-031 / AC-17a / AC-17b).

Usage:

    cd backend && uv run python -m scripts.test_card_file_size --size 4_3
    cd backend && uv run python -m scripts.test_card_file_size --size 9_16 --max-outlines 8

The script uses :class:`app.services.card_renderer.CardRenderer` — the
in-process deterministic fallback when sharp / satori are not
installed, so it runs in the test environment without npm install.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.services.card_renderer.renderer import (
    FILE_SIZE_BUDGET_BYTES,
    CardRenderer,
)


def _build_synthetic_plan(*, max_outlines: int) -> dict:
    """Build a worst-case InterviewPlan matching AC-17b's 7-8 outline spec."""
    outlines = [
        f"Outline #{i + 1}: 分布式事务 / 微服务 / RAG / Kafka / Redis / JVM / MySQL 的实战细节与生产经验，考察候选人对技术栈的整体掌握深度与系统设计能力。"
        for i in range(max(1, max_outlines))
    ]
    return {
        "target_company": "字节跳动 (ByteDance)",
        "target_position": "高级后端工程师 — 分布式系统方向",
        "job_requirements": "具备 5 年以上 Java/Go 后端开发经验，主导过亿级 QPS 的微服务架构演进，熟悉 Kafka / Redis / MySQL / PostgreSQL 等中间件的原理与调优。",
        "tech_stack": ["Java", "Go", "Kafka", "Redis", "PostgreSQL", "Kubernetes"],
        "interview_difficulty": "hard",
        "estimated_duration_minutes": 45,
        "focus_areas": [
            {"area": "分布式系统设计", "weight": 0.30, "reason": "岗位核心能力"},
            {"area": "高并发架构", "weight": 0.25, "reason": "亿级 QPS 场景"},
            {"area": "数据一致性", "weight": 0.20, "reason": "事务 / 锁 / 幂等"},
            {"area": "故障排查", "weight": 0.15, "reason": "生产稳定性"},
            {"area": "工程效能", "weight": 0.10, "reason": "CI/CD / 监控"},
        ],
        "suggested_questions": outlines,
        "tips": [
            "准备好 2-3 个你主导过的亿级 QPS 系统设计案例",
            "重点展示你对 Kafka exactly-once 语义 + Redis 集群脑裂 + 分布式事务的真实理解",
            "故障排查要有具体的 trace / log / metric 三位一体证据链",
        ],
        "web_research_summary": "字节跳动 2026 校招/社招面试 3-5 轮，技术深度考察偏多，业务理解次之。",
    }


async def _render_and_check(size: str, max_outlines: int) -> dict:
    plan = _build_synthetic_plan(max_outlines=max_outlines)
    renderer = CardRenderer()
    rendered = await renderer.render(plan, size_variant=size)
    return {
        "size_variant": rendered.size_variant,
        "width": rendered.width,
        "height": rendered.height,
        "bytes_total": rendered.bytes_total,
        "sha256_hex": rendered.sha256_hex,
        "budget_bytes": FILE_SIZE_BUDGET_BYTES,
        "passed": rendered.bytes_total <= FILE_SIZE_BUDGET_BYTES,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="REQ-048 US4 AC-17a / AC-17b card file-size budget assertion.",
    )
    parser.add_argument(
        "--size",
        required=True,
        choices=("4_3", "9_16"),
        help="Card size variant",
    )
    parser.add_argument(
        "--max-outlines",
        type=int,
        default=8,
        help="Outline count (worst case per AC-17b)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(_render_and_check(args.size, args.max_outlines))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"[{status}] size={result['size_variant']} "
            f"({result['width']}x{result['height']}) bytes={result['bytes_total']}/{result['budget_bytes']} "
            f"sha256={result['sha256_hex'][:12]}…"
        )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main"]