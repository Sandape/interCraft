"""Phase 6 — Content endpoints: resources, help FAQ, search."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user
from app.modules.content.schemas import (
    FaqDetailOut,
    FaqCategory,
    FaqItem,
    FaqListResponse,
    ResourceDetailOut,
    ResourceListResponse,
    ResourceOut,
    SearchResponse,
    SearchResultItem,
)
from app.modules.content.service import ContentService

router = APIRouter()


@router.get("/resources", status_code=200)
async def list_resources(
    category: str | None = Query(None),
    tag: str | None = Query(None),
    content_type: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(db_session_user_dep),
    user = Depends(get_current_user),
) -> ResourceListResponse:
    svc = ContentService(db)
    items, total = await svc.list_resources(
        category=category, tag=tag, content_type=content_type, limit=limit, offset=offset
    )

    return ResourceListResponse(
        items=[
            ResourceOut(
                id=r.id,
                title=r.title,
                summary=r.summary,
                category=r.category,
                tags=r.tags,
                content_type=r.content_type,
                read_time_minutes=r.read_time_minutes,
                sort_order=r.sort_order,
                created_at=r.created_at,
            )
            for r in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/resources/{resource_id}", status_code=200)
async def get_resource(
    resource_id: UUID,
    db: AsyncSession = Depends(db_session_user_dep),
    user = Depends(get_current_user),
) -> ResourceDetailOut:
    svc = ContentService(db)
    resource = await svc.get_resource(resource_id)
    if resource is None:
        raise HTTPException(404, detail="资源不存在")

    related = await svc.get_related_resources(resource)

    return ResourceDetailOut(
        id=resource.id,
        title=resource.title,
        summary=resource.summary,
        category=resource.category,
        tags=resource.tags,
        content_type=resource.content_type,
        content=resource.content,
        read_time_minutes=resource.read_time_minutes,
        video_url=resource.video_url,
        sort_order=resource.sort_order,
        created_at=resource.created_at,
        related_resources=[{"id": r.id, "title": r.title} for r in related],
    )


@router.get("/help/faq", status_code=200)
async def list_faq(
    category: str | None = Query(None),
    db: AsyncSession = Depends(db_session_user_dep),
    user = Depends(get_current_user),
) -> FaqListResponse:
    svc = ContentService(db)
    faqs = await svc.list_faq(category=category)

    # Group by category
    categories_map: dict[str, list[FaqItem]] = {}
    for faq in faqs:
        if faq.category not in categories_map:
            categories_map[faq.category] = []
        categories_map[faq.category].append(
            FaqItem(id=faq.id, question=faq.question, category=faq.category, sort_order=faq.sort_order)
        )

    return FaqListResponse(
        categories=[
            FaqCategory(
                category=cat,
                label=ContentService.CATEGORY_LABELS.get(cat, cat),
                items=items,
            )
            for cat, items in categories_map.items()
        ]
    )


@router.get("/help/faq/{faq_id}", status_code=200)
async def get_faq(
    faq_id: UUID,
    db: AsyncSession = Depends(db_session_user_dep),
    user = Depends(get_current_user),
) -> FaqDetailOut:
    svc = ContentService(db)
    faq = await svc.get_faq(faq_id)
    if faq is None:
        raise HTTPException(404, detail="FAQ 不存在")

    return FaqDetailOut(
        id=faq.id,
        question=faq.question,
        answer=faq.answer,
        category=faq.category,
        sort_order=faq.sort_order,
        created_at=faq.created_at,
    )


@router.get("/help/search", status_code=200)
async def search_help(
    q: str = Query(..., min_length=1),
    scope: str = Query("all", regex="^(faq|resources|all)$"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(db_session_user_dep),
    user = Depends(get_current_user),
) -> SearchResponse:
    svc = ContentService(db)
    results = await svc.search(q, scope=scope, limit=limit)

    return SearchResponse(
        faq=[
            SearchResultItem(id=r["id"], question=r["question"], category=r["category"], score=r["score"])
            for r in results.get("faq", [])
        ],
        resources=[
            SearchResultItem(id=r["id"], title=r["title"], category=r["category"], score=r["score"])
            for r in results.get("resources", [])
        ],
    )
