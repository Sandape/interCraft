"""Phase 7 — Global search HTTP endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep
from app.core.rate_limit import enforce_rate_limit
from app.modules.search.schemas import SearchResponse
from app.modules.search.service import SearchService

router = APIRouter()


@router.get("/search", response_model=SearchResponse, status_code=200)
async def search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(5, ge=1, le=5),
    db: AsyncSession = Depends(db_session_user_dep),
) -> SearchResponse:
    await enforce_rate_limit(request, scope="business")
    svc = SearchService(db)
    payload = await svc.search(query=q, per_type_limit=limit)
    return SearchResponse(**payload)


__all__ = ["router"]
