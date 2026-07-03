"""M15 — Interview WebSocket handler (T033).

Endpoint: /api/v1/ws/interview?token=<access_token>

Client → Server:
  - submit_answer: trigger score → condition → question_gen or report
  - reconnect: resume from last checkpoint

Server → Client:
  - node.started / token.delta / node.completed / error
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.agents.interview.graph import get_interview_graph
from app.api.deps import get_current_user_ws
from app.core.db import get_session_factory
from app.core.ws import connection_manager
from app.core.ws_events import (
    make_error_event,
    make_node_completed,
    make_node_started,
    make_token_delta,
    serialize_event,
)
from app.domain.interview_report import InterviewReportCreate
from app.domain.rls import set_user_context
from app.modules.interviews.repository import InterviewSessionRepository
from app.modules.interviews.service import sync_ability_dimensions
from app.repositories.interview_report_repo import InterviewReportRepo

logger = structlog.get_logger("interview.ws")

router = APIRouter()


@router.websocket("/ws/interview")
async def ws_interview(
    websocket: WebSocket,
    token: str = Query(default=""),
):
    """Interview WebSocket endpoint for real-time streaming."""
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        user_id = await get_current_user_ws(websocket, token=token)
    except WebSocketDisconnect:
        return

    device_id = websocket.query_params.get("device_id", "ws-unknown")

    await connection_manager.connect(user_id, device_id, websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    serialize_event(
                        make_error_event(
                            session_id="unknown",
                            node_name="system",
                            code="ws.invalid_json",
                            message="Invalid JSON",
                        )
                    )
                )
                continue

            msg_type = msg.get("type", "")

            if msg_type == "submit_answer":
                await _handle_submit_answer(websocket, user_id, msg)
            elif msg_type == "reconnect":
                await _handle_reconnect(websocket, user_id, msg)
            else:
                await websocket.send_text(
                    serialize_event(
                        make_error_event(
                            session_id=msg.get("session_id", "unknown"),
                            node_name="system",
                            code="ws.unknown_message_type",
                            message=f"Unknown message type: {msg_type}",
                        )
                    )
                )
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(user_id, device_id)


async def _handle_submit_answer(websocket: WebSocket, user_id: str, msg: dict) -> None:
    """Process a submit_answer message."""
    session_id = msg.get("session_id", "")
    answer = msg.get("content", "")
    sequence_no = msg.get("sequence_no", 0)

    if not session_id or not answer:
        await websocket.send_text(
            serialize_event(
                make_error_event(
                    session_id=session_id,
                    node_name="system",
                    code="ws.invalid_message",
                    message="Missing session_id or content",
                )
            )
        )
        return

    graph = get_interview_graph()

    # Notify scoring started
    await websocket.send_text(
        serialize_event(
            make_node_started(session_id, "score", current_question=sequence_no)
        )
    )

    try:
        result = await graph.submit_answer(
            thread_id=session_id,
            answer=answer,
            sequence_no=sequence_no,
            user_id=user_id,
        )

        current_q = result.get("current_question", 0)
        scores = result.get("scores", [])

        # Notify score completed
        latest_score = scores[-1] if scores else {}
        await websocket.send_text(
            serialize_event(
                make_node_completed(
                    session_id,
                    "score",
                    checkpoint_id=result.get("checkpoint_id", ""),
                    summary={
                        "question_no": sequence_no,
                        "score": latest_score.get("score", 0),
                        "dimension": latest_score.get("dimension", ""),
                        "feedback": latest_score.get("feedback", ""),
                        "sub_scores": latest_score.get("sub_scores", {}),
                    },
                )
            )
        )

        if len(scores) >= 5:
            # Interview complete → report
            await websocket.send_text(
                serialize_event(make_node_started(session_id, "report"))
            )
            overall = result.get("overall_score", 0)
            report = result.get("interview_report", {})

            # Persist report + update session status
            try:
                session_uuid = UUID(session_id)
                user_uuid = UUID(user_id)
                factory = get_session_factory()
                async with factory() as db:
                    await set_user_context(db, user_id)
                    # Update session status to completed
                    repo = InterviewSessionRepository(db)
                    session = await repo.get(session_uuid, user_uuid)
                    if session:
                        now = datetime.now(UTC)
                        duration = int((now - session.started_at).total_seconds()) if session.started_at else 0
                        await repo.update_status(
                            session_uuid, "completed",
                            ended_at=now, duration_sec=duration, overall_score=float(overall),
                        )

                    # Save report (create() handles commit)
                    report_repo = InterviewReportRepo(db)
                    await report_repo.create(InterviewReportCreate(
                        overall_score=float(overall),
                        per_question_score=report.get("per_question_score", []),
                        dimension_scores=report.get("dimension_scores", {}),
                        strengths=report.get("strengths", []),
                        improvements=report.get("improvements", []),
                        summary_md=report.get("summary_md", ""),
                        session_id=session_uuid,
                    ))

                    # Sync ability_dimensions so /ability-profile reflects the
                    # new scores immediately. The async arq job below is best-
                    # effort and may not run if the worker isn't up; this
                    # synchronous upsert is the source of truth.
                    await sync_ability_dimensions(db, session_uuid, user_uuid)
            except Exception as persist_err:
                logger.error("ws.report_persist_error", error=str(persist_err), session_id=session_id)

            # Enqueue ability diagnosis so the dashboard reflects interview scores.
            # Best-effort — failure here must not break the WS response.
            try:
                from app.core.redis import enqueue_job
                await enqueue_job(
                    "ability_diagnose",
                    user_id=str(user_id),
                    session_id=str(session_id),
                )
            except Exception:
                logger.warning("ability_diagnose.enqueue_failed", exc_info=True)

            await websocket.send_text(
                serialize_event(
                    make_node_completed(
                        session_id,
                        "report",
                        checkpoint_id=result.get("checkpoint_id", ""),
                        summary={
                            "overall_score": overall,
                            "report_id": report.get("report_id", ""),
                        },
                    )
                )
            )
        else:
            # Next question
            questions = result.get("questions", [])
            await websocket.send_text(
                serialize_event(
                    make_node_started(session_id, "question_gen", current_question=current_q)
                )
            )
            if questions:
                latest_q = questions[-1]
                await websocket.send_text(
                    serialize_event(
                        make_token_delta(session_id, "question_gen", latest_q.get("question", ""), 0)
                    )
                )
            await websocket.send_text(
                serialize_event(
                    make_node_completed(
                        session_id,
                        "question_gen",
                        checkpoint_id=result.get("checkpoint_id", ""),
                        summary={
                            "question_no": current_q,
                            "dimension": latest_q.get("dimension", "") if questions else "",
                            "question": latest_q.get("question", "") if questions else "",
                            "expected_points": latest_q.get("expected_points", []) if questions else [],
                            "hints": latest_q.get("hints", []) if questions else [],
                        },
                    )
                )
            )
    except Exception as exc:
        logger.error("ws.submit_answer_error", error=str(exc), session_id=session_id)
        await websocket.send_text(
            serialize_event(
                make_error_event(
                    session_id=session_id,
                    node_name="score",
                    code="internal_error",
                    message=str(exc),
                    retryable=True,
                )
            )
        )


async def _handle_reconnect(websocket: WebSocket, user_id: str, msg: dict) -> None:
    """Process a reconnect message."""
    session_id = msg.get("session_id", "")
    last_checkpoint_id = msg.get("last_seen_checkpoint_id")

    if not session_id:
        await websocket.send_text(
            serialize_event(
                make_error_event(
                    session_id=session_id,
                    node_name="system",
                    code="ws.invalid_message",
                    message="Missing session_id",
                )
            )
        )
        return

    graph = get_interview_graph()
    try:
        state = await graph.resume_from_checkpoint(
            thread_id=session_id,
            last_seen_checkpoint_id=last_checkpoint_id,
        )
    except Exception as exc:
        await websocket.send_text(
            serialize_event(
                make_error_event(
                    session_id=session_id,
                    node_name="system",
                    code="internal_error",
                    message=f"Resume failed: {exc}",
                )
            )
        )
        return

    next_node = state.get("next_node")
    current_q = state.get("current_question", 0)

    # REQ-041 AC-3.4 / AC-3.7a: project the typed ``error`` envelope into
    # the WS reconnect path. The interview graph is exposed via WebSocket
    # (not REST), so the wiring point is ``_handle_reconnect`` rather than
    # a REST GET /state endpoint. Closes the SC-002 wiring gap for the
    # 5th agent API surface.
    from app.agents.utils.node_error import serialize_state_error

    err = state.get("error")
    err_legacy = state.get("error_legacy")
    serialized = serialize_state_error(state_error=err, state_error_legacy=err_legacy)

    if next_node:
        await websocket.send_text(
            serialize_event(
                make_node_started(session_id, next_node, current_question=current_q)
            )
        )
    if serialized:
        # Surface error envelope so front-end can render ``error_category``
        # + ``node_name`` + ``error_legacy_str`` on reconnect failures.
        await websocket.send_text(
            serialize_event(
                make_error_event(
                    session_id=session_id,
                    node_name=serialized.get("node_name", "system"),
                    code=f"state.{serialized.get('error_category', 'unknown')}",
                    message=serialized.get("cause", ""),
                    retryable=serialized.get("error_category") == "timeout"
                    or serialized.get("error_category") == "checkpointer_unavailable",
                )
            )
        )


__all__ = ["router"]
