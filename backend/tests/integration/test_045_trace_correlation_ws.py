from __future__ import annotations

import pytest
from fastapi import WebSocketDisconnect

from app.api.v1.ws.interview import build_ws_trace_context


def test_websocket_message_trace_context_prefers_message_trace_id() -> None:
    ctx = build_ws_trace_context(
        {"trace_id": "2" * 32, "run_id": "run-ws"},
        fallback_run_id="session-1",
    )

    assert ctx.trace_id == "2" * 32
    assert ctx.run_id == "run-ws"


def test_websocket_message_trace_context_generates_safe_fallback() -> None:
    ctx = build_ws_trace_context({}, fallback_run_id="session-1")

    assert ctx.run_id == "session-1"
    assert ctx.trace_id is not None
    assert len(ctx.trace_id) == 32


@pytest.mark.asyncio
async def test_submit_answer_stops_when_client_disconnects(monkeypatch) -> None:
    from app.api.v1.ws import interview as interview_ws

    class FakeGraph:
        async def submit_answer(self, **kwargs):
            return {
                "current_question": 1,
                "scores": [],
                "questions": [
                    {
                        "question": "Q1",
                        "dimension": "技术深度",
                        "expected_points": ["point"],
                        "hints": [],
                    }
                ],
                "checkpoint_id": "checkpoint-1",
            }

    class DisconnectingWebSocket:
        def __init__(self) -> None:
            self.send_count = 0

        async def send_text(self, text: str) -> None:
            self.send_count += 1
            if self.send_count == 2:
                raise WebSocketDisconnect(code=1000)

    fake_websocket = DisconnectingWebSocket()
    monkeypatch.setattr(interview_ws, "get_interview_graph", lambda: FakeGraph())

    with pytest.raises(WebSocketDisconnect):
        await interview_ws._handle_submit_answer(
            fake_websocket,
            "019f366f-badb-7a4d-87ab-d0a30f392541",
            {
                "session_id": "not-a-uuid",
                "content": "answer",
                "sequence_no": 0,
                "trace_id": "1" * 32,
            },
        )

    assert fake_websocket.send_count == 2
