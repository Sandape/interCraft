"""Short-answer score fast path (REQ-058 T029)."""
from __future__ import annotations

import pytest

from app.agents.interview.nodes.score_llm import score_llm_node


@pytest.mark.asyncio
async def test_empty_answer_fast_score(monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom:
        async def invoke(self, *args, **kwargs):
            raise AssertionError("should not call LLM")

    monkeypatch.setattr(
        "app.agents.interview.nodes.score_llm.get_llm_client",
        lambda: Boom(),
    )
    out = await score_llm_node(
        {
            "questions": [
                {
                    "question": "请介绍分布式事务",
                    "dimension": "architecture",
                    "expected_points": ["一致性", "补偿"],
                }
            ],
            "scores": [],
            "current_question": 1,
            "messages": [{"role": "user", "content": "", "sequence_no": 1}],
            "user_id": "u",
            "thread_id": "t",
        }
    )
    assert out["raw_score"] <= 2
    assert out["scores"][-1]["off_topic"] is True
    assert out["scores"][-1]["scoring_method"] == "local_short_answer"


@pytest.mark.asyncio
async def test_short_answer_fast_score(monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom:
        async def invoke(self, *args, **kwargs):
            raise AssertionError("should not call LLM")

    monkeypatch.setattr(
        "app.agents.interview.nodes.score_llm.get_llm_client",
        lambda: Boom(),
    )
    out = await score_llm_node(
        {
            "questions": [{"question": "Q", "dimension": "tech_depth", "expected_points": ["a"]}],
            "scores": [],
            "current_question": 1,
            "messages": [{"role": "user", "content": "不知道", "sequence_no": 1}],
            "user_id": "u",
            "thread_id": "t",
        }
    )
    assert out["raw_score"] <= 2
    assert out["scores"][-1]["scoring_method"] == "local_short_answer"


@pytest.mark.asyncio
async def test_degraded_template_answer_scores_without_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Boom:
        async def invoke(self, *args, **kwargs):
            raise AssertionError("degraded template path must not call LLM")

    monkeypatch.setattr(
        "app.agents.interview.nodes.score_llm.get_llm_client",
        lambda: Boom(),
    )
    out = await score_llm_node(
        {
            "questions": [
                {
                    "question": "请结合一个真实项目，分享你在技术深度方面的实践。",
                    "dimension": "tech_depth",
                    "expected_points": [],
                    "source": "template_degraded",
                }
            ],
            "scores": [],
            "current_question": 1,
            "degraded": True,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "我在企业级 Agent 工作流平台里负责过意图识别、工具选择、"
                        "参数校验和执行回写。我把流程拆成 LangGraph 状态节点，"
                        "并用日志、离线回放和线上采样验证工具命中率、失败恢复率。"
                    ),
                    "sequence_no": 1,
                }
            ],
            "user_id": "u",
            "thread_id": "t",
        }
    )

    assert out["raw_score"] >= 6
    assert out["scores"][-1]["source"] == "template_degraded"
    assert "local_degraded" in out["scores"][-1]["scoring_method"]
