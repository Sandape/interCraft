"""M17 — Error Coach REST endpoints.

POST /api/v1/agents/error-coach/start
POST /api/v1/agents/error-coach/{thread_id}/messages
POST /api/v1/agents/error-coach/{thread_id}/abort
GET  /api/v1/agents/error-coach/{thread_id}/state

Per contracts/agents-api.md.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from app.api.deps import get_current_user

router = APIRouter(prefix="/agents/error-coach", tags=["agents"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class StartRequest(BaseModel):
    error_question_id: str = Field(..., description="Error question UUID")


class StartResponse(BaseModel):
    thread_id: str
    status: str
    current_node: str | None = None
    # REQ-061 T086 — canonical control/detail links.
    runtime_links: dict[str, str] | None = None


class MessageRequest(BaseModel):
    content: str = Field(..., description="User answer text")


class MessageResponse(BaseModel):
    thread_id: str
    status: str
    current_node: str | None = None
    score: int | None = None
    correct_count: int | None = None
    hint_level: str | None = None
    hint_content: str | None = None
    runtime_links: dict[str, str] | None = None


class AbortResponse(BaseModel):
    thread_id: str
    status: str
    correct_count_achieved: int | None = None
    runtime_links: dict[str, str] | None = None


class StateResponse(BaseModel):
    thread_id: str
    status: str
    correct_count: int | None = None
    attempt_count: int | None = None
    current_hint_level: str | None = None
    runtime_links: dict[str, str] | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/start", status_code=201)
async def error_coach_start(
    body: StartRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Start error coach session for a specific error question."""
    from app.agents.graphs.error_coach import get_error_coach_graph
    from app.modules.ai_runtime.adapters.error_coach import runtime_links_for_thread

    user_id = str(current_user.id)
    graph = get_error_coach_graph()

    try:
        thread_id = await graph.start(
            user_id=user_id,
            error_question_id=body.error_question_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return StartResponse(
        thread_id=thread_id,
        status="running",
        current_node="fetch_question",
        runtime_links=runtime_links_for_thread(thread_id),
    )


@router.post("/{thread_id}/messages")
async def error_coach_messages(
    thread_id: str,
    body: MessageRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Submit user answer in error coach session."""
    from app.agents.graphs.error_coach import get_error_coach_graph
    from app.modules.ai_runtime.adapters.error_coach import runtime_links_for_thread

    graph = get_error_coach_graph()
    try:
        result = await graph.submit_answer(thread_id, body.content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return MessageResponse(
        thread_id=thread_id,
        status=result.get("status", "running"),
        current_node=result.get("current_node"),
        score=result.get("score"),
        correct_count=result.get("correct_count"),
        hint_level=result.get("hint_level"),
        hint_content=result.get("hint_content"),
        runtime_links=runtime_links_for_thread(thread_id),
    )


@router.post("/{thread_id}/abort")
async def error_coach_abort(
    thread_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """User-initiated abort for error coach session."""
    from app.agents.graphs.error_coach import get_error_coach_graph
    from app.modules.ai_runtime.adapters.error_coach import runtime_links_for_thread

    graph = get_error_coach_graph()
    try:
        result = await graph.abort(thread_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return AbortResponse(
        thread_id=thread_id,
        status="aborted",
        correct_count_achieved=result.get("correct_count", 0),
        runtime_links=runtime_links_for_thread(thread_id),
    )


@router.get("/{thread_id}/state")
async def error_coach_state(
    thread_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get current state of error coach session."""
    from app.agents.graphs.error_coach import get_error_coach_graph
    from app.agents.utils.node_error import serialize_state_error
    from app.modules.ai_runtime.adapters.error_coach import runtime_links_for_thread

    graph = get_error_coach_graph()
    try:
        state = await graph.get_state(thread_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # REQ-041 AC-3.4 / AC-3.7a: project ``state["error"]`` (and the
    # dual-track ``error_legacy`` for interview, N/A here) into API
    # ``error_category`` + ``node_name`` + ``cause`` + ``retry_after``
    # fields. Without this wiring, SC-002 "100% fill rate" is 0% — the
    # helper exists in ``app.agents.utils.node_error`` but no API path
    # was invoking it.
    err = state.pop("error", None)
    serialized = serialize_state_error(state_error=err, state_error_legacy=None)
    return {
        **state,
        **serialized,
        "runtime_links": runtime_links_for_thread(thread_id),
    }
