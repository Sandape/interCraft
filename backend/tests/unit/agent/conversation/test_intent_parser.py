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
async def test_parse_create_job_json():
    llm = AsyncMock()
    llm.invoke = AsyncMock(
        return_value={
            "content": '{"intent":"create_job","entities":{"company":"腾讯","position":"后端"},"confidence":0.92,"alternatives":[]}'
        }
    )
    parser = IntentParser(llm_client=llm)
    r = await parser.parse("帮我记一个腾讯的后端岗", user_id=uuid4())
    assert r["intent"] == "create_job"
    assert r["entities"]["company"] == "腾讯"
    assert r["confidence"] >= CONFIDENCE_THRESHOLD
    llm.invoke.assert_awaited()
    call_kwargs = llm.invoke.await_args.kwargs
    assert call_kwargs["node_name"] == "intent_parse"


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
    r = await parser.parse("我的求职进展", user_id=uuid4())
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
async def test_delete_mapped_to_web_guide():
    llm = AsyncMock()
    llm.invoke = AsyncMock(
        return_value={
            "content": '{"intent":"delete_job","entities":{"company":"腾讯"},"confidence":0.9,"alternatives":[]}'
        }
    )
    parser = IntentParser(llm_client=llm)
    r = await parser.parse("删掉腾讯那个岗", user_id=uuid4())
    assert r["intent"] == "rejected_web_guide"
    assert "delete" in r["entities"].get("guide", "")
    assert WEB_GUIDE_DELETE in r["entities"].get("reply", "")


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
