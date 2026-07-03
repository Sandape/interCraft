"""M16 — Resume Optimize REST endpoints.

POST /api/v1/agents/resume-optimize/start
POST /api/v1/agents/resume-optimize/{thread_id}/confirm
GET  /api/v1/agents/resume-optimize/{thread_id}/state

Per contracts/agents-api.md.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from app.api.deps import get_current_user

router = APIRouter(prefix="/agents/resume-optimize", tags=["agents"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class StartRequest(BaseModel):
    branch_id: str = Field(..., description="Target resume branch UUID")
    target_jd: str | None = Field(None, description="JD description")
    company: str | None = Field(None, description="Company name (if no target_jd)")
    position: str | None = Field(None, description="Position name (if no target_jd)")


class StartResponse(BaseModel):
    thread_id: str
    status: str
    current_node: str | None = None


class ConfirmRequest(BaseModel):
    decision: str = Field(..., pattern="^(apply|discard)$")
    # US5: per-patch selection. None or omitted = apply all patches.
    accepted_patch_indices: list[int] | None = Field(
        None,
        description="Indices of patches to apply (0-based). None = apply all. Only valid with decision=apply.",
    )


class ConfirmResponse(BaseModel):
    thread_id: str
    status: str
    decision: str
    version_id: str | None = None


class StateResponse(BaseModel):
    thread_id: str
    status: str
    current_node: str | None = None
    summary: str | None = None
    proposed_patches: list | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/start", status_code=201)
async def resume_optimize_start(
    body: StartRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Start resume optimization agent."""
    from uuid import UUID

    user_id = str(current_user.id)
    branch_id = body.branch_id
    target_jd = body.target_jd or f"{body.position or ''} at {body.company or ''}".strip()

    if not target_jd:
        raise HTTPException(status_code=422, detail="target_jd or (company + position) required")

    # Check branch exists
    from app.core.db import get_session_factory
    from app.domain.rls import set_user_context
    from sqlalchemy import text

    factory = get_session_factory()
    async with factory() as session:
        await set_user_context(session, user_id)
        result = await session.execute(
            text("SELECT id FROM resume_branches WHERE id = :bid AND deleted_at IS NULL"),
            {"bid": UUID(branch_id)},
        )
        if result.fetchone() is None:
            raise HTTPException(status_code=404, detail="Resume branch not found")

    from app.agents.graphs.resume_optimize import get_resume_optimize_graph

    graph = get_resume_optimize_graph()
    try:
        thread_id = await graph.start(
            user_id=user_id,
            branch_id=branch_id,
            target_jd=target_jd,
        )
    except Exception as exc:
        if "locked" in str(exc).lower():
            raise HTTPException(status_code=423, detail="Resume branch is locked by another session")
        raise HTTPException(status_code=500, detail=str(exc))

    return StartResponse(thread_id=thread_id, status="running", current_node="load_branch")


@router.post("/{thread_id}/confirm")
async def resume_optimize_confirm(
    thread_id: str,
    body: ConfirmRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Resolve interrupt — apply or discard proposed patches."""
    from app.agents.graphs.resume_optimize import get_resume_optimize_graph

    graph = get_resume_optimize_graph()
    try:
        result = await graph.confirm(
            thread_id,
            body.decision,
            accepted_patch_indices=body.accepted_patch_indices,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return ConfirmResponse(
        thread_id=thread_id,
        status="completed",
        decision=body.decision,
        version_id=str(result.get("version_id", "")) if body.decision == "apply" else None,
    )


@router.get("/{thread_id}/state")
async def resume_optimize_state(
    thread_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get current state of the resume optimization agent."""
    from app.agents.graphs.resume_optimize import get_resume_optimize_graph
    from app.agents.utils.node_error import serialize_state_error

    graph = get_resume_optimize_graph()
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
