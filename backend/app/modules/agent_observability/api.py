"""REQ-051: simplified auth — all endpoints use single ``require_admin`` dependency."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.admin_console.auth import get_caller_user_id_dep, require_admin
from app.modules.agent_observability.schemas import PayloadRevealBody, TraceSearchFilters
from app.modules.agent_observability.payloads import PayloadRevealDenied, PayloadRevealExpired
from app.modules.agent_observability import service

router = APIRouter()
eval_center_router = APIRouter()


@router.get("/health", status_code=200)
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "agent_observability"}


@router.get("/traces")
async def traces(
    q: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    feature_area: str | None = Query(default=None),
    status: str | None = Query(default=None),
    eval_status: str | None = Query(default=None),
    badcase_status: str | None = Query(default=None),
    privacy_class: str | None = Query(default=None),
    _admin: Annotated[bool, Depends(require_admin)] = True,
) -> dict:
    return service.search_traces(
        TraceSearchFilters(
            q=q,
            cursor=cursor,
            limit=limit,
            feature_area=feature_area,
            status=status,
            eval_status=eval_status,
            badcase_status=badcase_status,
            privacy_class=privacy_class,
        )
    )


@router.get("/traces/{trace_id}")
async def trace_detail(
    trace_id: str,
    _admin: Annotated[bool, Depends(require_admin)] = True,
) -> dict:
    return service.get_trace_detail(trace_id)


@router.get("/agent-runs/{agent_run_id}")
async def agent_run_detail(
    agent_run_id: str,
    _admin: Annotated[bool, Depends(require_admin)] = True,
) -> dict:
    return {
        "agent_run_id": agent_run_id,
        "trace_id": service.DEMO_TRACE_ID,
        "agent_name": "interview_supervisor",
        "graph": "interview",
        "status": "error",
        "nodes": [service.get_node_detail("span_node_score")],
    }


@router.get("/nodes/{span_id}")
async def node_detail(
    span_id: str,
    _admin: Annotated[bool, Depends(require_admin)] = True,
) -> dict:
    return service.get_node_detail(span_id)


@router.get("/llm-calls/{llm_call_id}")
async def llm_call_detail(
    llm_call_id: str,
    _admin: Annotated[bool, Depends(require_admin)] = True,
) -> dict:
    return service.get_llm_call_detail(llm_call_id)


@router.post("/payloads/{payload_id}/reveal")
async def reveal_payload(
    payload_id: str,
    payload: PayloadRevealBody,
    _admin: Annotated[bool, Depends(require_admin)] = True,
    user_id: Annotated[UUID, Depends(get_caller_user_id_dep)] = UUID("00000000-0000-0000-0000-000000000000"),
) -> dict:
    if not payload.reason.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="reason is required")
    try:
        return await service.reveal_payload(payload_id=payload_id, actor_user_id=str(user_id), reason=payload.reason)
    except PayloadRevealExpired as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except PayloadRevealDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/llm-calls/{llm_call_id}/curl")
async def llm_curl(
    llm_call_id: str,
    reason: str = Query(...),
    _admin: Annotated[bool, Depends(require_admin)] = True,
    user_id: Annotated[UUID, Depends(get_caller_user_id_dep)] = UUID("00000000-0000-0000-0000-000000000000"),
) -> dict:
    if not reason.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="reason is required")
    return await service.get_llm_curl(llm_call_id=llm_call_id, actor_user_id=str(user_id), reason=reason)


@router.get("/coverage")
async def coverage(
    environment: str = Query(default="production"),
    _admin: Annotated[bool, Depends(require_admin)] = True,
) -> dict:
    return service.build_coverage_report(environment=environment).to_contract_dict()


@eval_center_router.get("/runs")
async def eval_runs(
    _admin: Annotated[bool, Depends(require_admin)] = True,
) -> dict:
    return service.list_eval_runs()


@eval_center_router.get("/runs/{eval_run_id}")
async def eval_run_detail(
    eval_run_id: str,
    _admin: Annotated[bool, Depends(require_admin)] = True,
) -> dict:
    return service.get_eval_run(eval_run_id)


@eval_center_router.get("/cases/{case_result_id}")
async def eval_case_detail(
    case_result_id: str,
    _admin: Annotated[bool, Depends(require_admin)] = True,
) -> dict:
    return service.get_eval_case(case_result_id)


@eval_center_router.get("/gate/latest")
async def latest_eval_gate(
    _admin: Annotated[bool, Depends(require_admin)] = True,
) -> dict:
    return service.get_latest_eval_gate()


__all__ = ["eval_center_router", "router"]
