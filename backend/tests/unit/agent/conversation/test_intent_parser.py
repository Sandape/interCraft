"""Unit tests for intent_parser with mocked LLM."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.agent.conversation.intent_parser import (
    CONFIDENCE_THRESHOLD,
    IntentParser,
)
from app.modules.agent.conversation.reply_formatter import WEB_GUIDE_DELETE, WEB_GUIDE_OFFER


@pytest.mark.asyncio
async def test_rule_confirm_cancel_without_llm():
    parser = IntentParser(llm_client=MagicMock())
    uid = uuid4()
    r = await parser.parse("确认", user_id=uid)
    assert r["intent"] == "confirm"
    assert r["confidence"] == 1.0

    r2 = await parser.parse("取消", user_id=uid)
    assert r2["intent"] == "cancel"


@pytest.mark.asyncio
async def test_help_keyword():
    parser = IntentParser(llm_client=MagicMock())
    r = await parser.parse("帮助", user_id=uuid4())
    assert r["intent"] == "help"


@pytest.mark.asyncio
async def test_rule_create_job_without_llm():
    llm = AsyncMock()
    parser = IntentParser(llm_client=llm)
    r = await parser.parse("帮我记一个腾讯的后端岗", user_id=uuid4())
    assert r["intent"] == "create_job"
    assert r["entities"]["company"] == "腾讯"
    assert "后端" in r["entities"]["position"]
    assert r["confidence"] >= CONFIDENCE_THRESHOLD
    llm.invoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_parse_create_job_json_via_llm_when_no_rule():
    llm = AsyncMock()
    llm.invoke = AsyncMock(
        return_value={
            "content": '{"intent":"create_job","entities":{"company":"腾讯","position":"后端"},"confidence":0.92,"alternatives":[]}'
        }
    )
    parser = IntentParser(llm_client=llm)
    # Phrasing that does not match deterministic create_job rules
    r = await parser.parse("想在腾讯做后端，帮我登记一下", user_id=uuid4())
    assert r["intent"] == "create_job"
    assert r["entities"]["company"] == "腾讯"
    assert r["confidence"] >= CONFIDENCE_THRESHOLD
    llm.invoke.assert_awaited()
    call_kwargs = llm.invoke.await_args.kwargs
    assert call_kwargs["node_name"] == "intent_parse"


@pytest.mark.asyncio
async def test_rule_query_jobs_without_llm():
    llm = AsyncMock()
    parser = IntentParser(llm_client=llm)
    r = await parser.parse("我的求职进展", user_id=uuid4())
    assert r["intent"] == "query_jobs"
    llm.invoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_on_parse_error_then_success():
    llm = AsyncMock()
    llm.invoke = AsyncMock(
        side_effect=[
            {"content": "not json"},
            {
                "content": '{"intent":"query_jobs","entities":{},"confidence":0.8,"alternatives":[]}'
            },
        ]
    )
    parser = IntentParser(llm_client=llm)
    # Avoid exact rule match so LLM path is exercised
    r = await parser.parse("最近投递情况怎么样", user_id=uuid4())
    assert r["intent"] == "query_jobs"
    assert llm.invoke.await_count == 2


@pytest.mark.asyncio
async def test_llm_unavailable_after_retry():
    llm = AsyncMock()
    llm.invoke = AsyncMock(side_effect=RuntimeError("timeout"))
    parser = IntentParser(llm_client=llm)
    r = await parser.parse("随便说点什么", user_id=uuid4())
    assert r["error"] == "llm_unavailable"
    assert r["intent"] == "unknown"
    assert llm.invoke.await_count == 2


@pytest.mark.asyncio
async def test_llm_unavailable_falls_back_to_rule():
    llm = AsyncMock()
    llm.invoke = AsyncMock(side_effect=RuntimeError("timeout"))
    parser = IntentParser(llm_client=llm)
    # skip_confirm_rules bypasses pre-LLM rules; post-failure fallback still applies
    r = await parser.parse(
        "新增岗位：腾讯，后端开发工程师",
        user_id=uuid4(),
        skip_confirm_rules=True,
    )
    assert r["intent"] == "create_job"
    assert r["entities"]["company"] == "腾讯"
    assert r["entities"]["position"] == "后端开发工程师"


@pytest.mark.asyncio
async def test_delete_mapped_to_web_guide():
    llm = AsyncMock()
    parser = IntentParser(llm_client=llm)
    r = await parser.parse("删掉腾讯那个岗位", user_id=uuid4())
    assert r["intent"] == "rejected_web_guide"
    assert "delete" in r["entities"].get("guide", "")
    assert WEB_GUIDE_DELETE in r["entities"].get("reply", "")
    llm.invoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_offer_mapped_to_web_guide():
    llm = AsyncMock()
    llm.invoke = AsyncMock(
        return_value={
            "content": '{"intent":"update_offer","entities":{},"confidence":0.88,"alternatives":[]}'
        }
    )
    parser = IntentParser(llm_client=llm)
    r = await parser.parse("填一下 offer 薪资", user_id=uuid4())
    assert r["intent"] == "rejected_web_guide"
    assert WEB_GUIDE_OFFER in r["entities"].get("reply", "")


@pytest.mark.asyncio
async def test_rule_update_status_进一面():
    llm = AsyncMock()
    parser = IntentParser(llm_client=llm)
    r = await parser.parse("字节进一面了", user_id=uuid4())
    assert r["intent"] == "update_status"
    assert r["entities"]["company"] == "字节"
    assert r["entities"]["target_status"] == "interview_1"
    llm.invoke.assert_not_awaited()
