"""M19 — General Coach REST endpoints.

POST /api/v1/agents/general-coach/start
POST /api/v1/agents/general-coach/{thread_id}/messages
POST /api/v1/agents/general-coach/{thread_id}/close
GET  /api/v1/agents/general-coach/{thread_id}/state

Per contracts/agents-api.md.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from app.api.deps import get_current_user

router = APIRouter(prefix="/agents/general-coach", tags=["agents"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class StartRequest(BaseModel):
    initial_question: str | None = Field(None, description="Optional initial question")


class StartResponse(BaseModel):
    thread_id: str
    conversation_id: str
    status: str


class MessageRequest(BaseModel):
    content: str = Field(..., description="User message text")


class MessageResponse(BaseModel):
    thread_id: str
    detected_intent: str | None = None
    confidence: float | None = None
    redirect_to: str | None = None


class CloseResponse(BaseModel):
    thread_id: str
    status: str


class StateResponse(BaseModel):
    thread_id: str
    detected_intent: str | None = None
    message_count: int | None = None
    session_active: bool | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/start", status_code=201)
async def general_coach_start(
    body: StartRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Start a general coach conversation."""
    from app.agents.graphs.general_coach import get_general_coach_graph

    user_id = str(current_user.id)
    graph = get_general_coach_graph()

    try:
        thread_id = await graph.start(
            user_id=user_id,
            initial_question=body.initial_question or "",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return StartResponse(
        thread_id=thread_id,
        conversation_id=thread_id,
        status="running",
    )


@router.post("/{thread_id}/messages")
async def general_coach_messages(
    thread_id: str,
    body: MessageRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Send a message in a general coach conversation."""
    from app.agents.graphs.general_coach import get_general_coach_graph

    graph = get_general_coach_graph()
    try:
        result = await graph.send_message(thread_id, body.content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return MessageResponse(
        thread_id=thread_id,
        detected_intent=result.get("detected_intent"),
        confidence=result.get("confidence"),
        redirect_to=result.get("suggested_redirect"),
    )


@router.post("/{thread_id}/close")
async def general_coach_close(
    thread_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Close a general coach conversation."""
    from app.agents.graphs.general_coach import get_general_coach_graph

    graph = get_general_coach_graph()
    try:
        await graph.close(thread_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return CloseResponse(thread_id=thread_id, status="closed")


@router.get("/{thread_id}/state")
async def general_coach_state(
    thread_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get current state of general coach conversation."""
    from app.agents.graphs.general_coach import get_general_coach_graph
    from app.agents.utils.node_error import serialize_state_error

    graph = get_general_coach_graph()
    try:
        state = await graph.get_state(thread_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # REQ-041 AC-3.4 / AC-3.7a: project ``state["error"]`` into the API
    # ``error_category`` + ``node_name`` + ``cause`` fields via
    # ``serialize_state_error``. Closes the SC-002 wiring gap where the
    # helper was defined but never invoked by any agent API endpoint.
    err = state.pop("error", None)
    serialized = serialize_state_error(state_error=err, state_error_legacy=None)
    return {**state, **serialized}
