"""Unit tests for plan question selection (REQ-058 T006/T007)."""
from __future__ import annotations

from app.agents.interview.plan_questions import (
    build_focus_schedule,
    select_next_question_spec,
)


SAMPLE_PLAN = {
    "target_company": "美团",
    "target_position": "后端工程师",
    "interview_difficulty": "medium",
    "focus_areas": [
        {"area": "分布式系统", "weight": 0.4, "reason": "核心"},
        {"area": "数据库", "weight": 0.3, "reason": "存储"},
        {"area": "工程实践", "weight": 0.2, "reason": "质量"},
        {"area": "沟通协作", "weight": 0.1, "reason": "软技能"},
    ],
    "suggested_questions": [
        "请描述一次你设计高并发接口的经历",
        "如何保证订单系统的最终一致性？",
        "MySQL 慢查询你会怎么排查？",
        "说说你们的 CI/CD 流水线",
        "如何做一次技术方案评审？",
        "Redis 缓存穿透怎么防？",
        "微服务拆分的边界如何定？",
    ],
    "tips": ["追问落地细节"],
    "tech_stack": ["Java", "Redis", "MySQL"],
}


def test_weight_schedule_respects_floor_counts() -> None:
    n = 10
    schedule = build_focus_schedule(SAMPLE_PLAN["focus_areas"], n)
    assert len(schedule) == n
    counts = {label: schedule.count(label) for label in {a["area"] for a in SAMPLE_PLAN["focus_areas"]}}
    # floor(0.4*10)=4, floor(0.3*10)=3, floor(0.2*10)=2, floor(0.1*10)=1 → sum 10
    assert counts["分布式系统"] >= 4
    assert counts["数据库"] >= 3
    assert counts["工程实践"] >= 2
    assert counts["沟通协作"] >= 1


def test_suggested_then_generated_for_n10() -> None:
    asked: list[dict] = []
    sources: list[str] = []
    for _ in range(10):
        spec = select_next_question_spec(
            interview_plan=SAMPLE_PLAN,
            plan_status="ready",
            degraded=False,
            questions=asked,
            max_questions=10,
            position="后端工程师",
            company="美团",
        )
        sources.append(spec.source)
        asked.append(
            {
                "question_no": spec.question_no,
                "question": spec.question or f"generated-{spec.question_no}",
                "source": spec.source,
                "dimension": spec.dimension,
            }
        )
    assert sources[:7] == ["suggested"] * 7
    assert sources[7:] == ["generated"] * 3
    assert all(
        select_next_question_spec(
            interview_plan=SAMPLE_PLAN,
            plan_status="ready",
            degraded=False,
            questions=asked[:i],
            max_questions=10,
        ).use_plan_block
        for i in range(10)
    )


def test_failed_plan_blocks_unless_degraded() -> None:
    blocked = select_next_question_spec(
        interview_plan=None,
        plan_status="failed",
        degraded=False,
        questions=[],
        max_questions=10,
    )
    assert blocked.source == "blocked"

    degraded = select_next_question_spec(
        interview_plan=None,
        plan_status="failed",
        degraded=True,
        questions=[],
        max_questions=10,
    )
    assert degraded.source == "template_degraded"


def test_degraded_without_plan_rotates_fallback_dimensions() -> None:
    asked: list[dict] = []
    dims: list[str] = []
    for _ in range(6):
        spec = select_next_question_spec(
            interview_plan=None,
            plan_status="degraded",
            degraded=True,
            questions=asked,
            max_questions=10,
        )
        dims.append(spec.dimension)
        asked.append(
            {
                "question_no": spec.question_no,
                "question": f"template-{spec.question_no}",
                "source": spec.source,
                "dimension": spec.dimension,
            }
        )

    assert dims[:5] == [
        "tech_depth",
        "architecture",
        "engineering_practice",
        "communication",
        "algorithm",
    ]
    assert dims[5] == "tech_depth"


def test_junk_company_stripped_from_suggested() -> None:
    plan = {
        **SAMPLE_PLAN,
        "suggested_questions": ["请谈谈你在 123123 的项目经验"],
    }
    spec = select_next_question_spec(
        interview_plan=plan,
        plan_status="ready",
        degraded=False,
        questions=[],
        max_questions=10,
        company="123123",
        position="后端",
    )
    assert spec.source == "suggested"
    assert spec.question is not None
    assert "123123" not in spec.question
