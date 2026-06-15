"""Ability dimensions REST API (M09).

6 endpoints:
- GET /ability-dimensions — list user dimensions
- GET /ability-dimensions/dimensions-meta — static metadata
- GET /ability-dimensions/history — time series
- GET /ability-dimensions/{key} — get single
- PATCH /ability-dimensions/{key} — update
- POST /ability-dimensions/{key}/toggle — enable/disable
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, db_session_user_dep
from app.modules.abilities.repository import AbilityDimensionRepository
from app.modules.abilities.schemas import (
    AbilityDimensionListOut,
    AbilityDimensionOut,
    AbilityHistoryListOut,
    DimensionsMetaOut,
    PatchAbilityDimensionInput,
    ToggleDimensionInput,
)
from app.modules.abilities.service import AbilityService

router = APIRouter(prefix="/ability-dimensions", tags=["abilities"])

DIMENSIONS_META_STATIC = {
    "dimensions": [
        {"key": "tech_depth", "label_zh": "技术深度", "label_en": "Technical Depth",
         "sub_keys": [{"key": "fundamentals", "label_zh": "基础知识"},
                      {"key": "system_design", "label_zh": "系统设计"},
                      {"key": "depth_specialty", "label_zh": "专精深度"}]},
        {"key": "architecture", "label_zh": "架构能力", "label_en": "Architecture",
         "sub_keys": [{"key": "decomposition", "label_zh": "模块拆解"},
                      {"key": "tradeoffs", "label_zh": "方案权衡"},
                      {"key": "scalability", "label_zh": "可扩展性"}]},
        {"key": "engineering_practice", "label_zh": "工程实践", "label_en": "Engineering Practice",
         "sub_keys": [{"key": "code_quality", "label_zh": "代码质量"},
                      {"key": "testing", "label_zh": "测试能力"},
                      {"key": "observability", "label_zh": "可观测性"}]},
        {"key": "communication", "label_zh": "沟通表达", "label_en": "Communication",
         "sub_keys": [{"key": "clarity", "label_zh": "清晰度"},
                      {"key": "structure", "label_zh": "结构化"},
                      {"key": "conciseness", "label_zh": "简洁性"}]},
        {"key": "algorithm", "label_zh": "算法能力", "label_en": "Algorithm",
         "sub_keys": [{"key": "data_structures", "label_zh": "数据结构"},
                      {"key": "complexity", "label_zh": "复杂度分析"},
                      {"key": "edge_cases", "label_zh": "边界处理"}]},
        {"key": "business", "label_zh": "业务理解", "label_en": "Business Acumen",
         "sub_keys": [{"key": "domain_knowledge", "label_zh": "行业知识"},
                      {"key": "product_sense", "label_zh": "产品思维"},
                      {"key": "user_empathy", "label_zh": "用户共情"}]},
    ]
}


def _get_service(session: AsyncSession = Depends(db_session_user_dep)) -> AbilityService:
    return AbilityService(AbilityDimensionRepository(session))


# ---- Concrete routes FIRST (before parameterized) ----

@router.get("/dimensions-meta", response_model=DimensionsMetaOut)
async def get_dimensions_meta() -> dict:
    return DIMENSIONS_META_STATIC


@router.get("/history", response_model=AbilityHistoryListOut)
async def get_history(
    dimension_key: str | None = Query(default=None),
    aggregate: str = Query(default="month"),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=20, ge=1, le=50),
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityService = Depends(_get_service),
) -> dict:
    data = await svc.history(
        user_id,
        dimension_key=dimension_key,
        aggregate=aggregate,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )
    return {"data": data}


# ---- Parameterized routes second ----

@router.get("", response_model=AbilityDimensionListOut)
async def list_dimensions(
    is_active: bool | None = Query(default=None),
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityService = Depends(_get_service),
) -> dict:
    data = await svc.read(user_id, is_active=is_active)
    return {"data": data}


@router.get("/{dimension_key}", response_model=AbilityDimensionOut)
async def get_dimension(
    dimension_key: str,
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityService = Depends(_get_service),
) -> dict:
    return await svc.get_by_key(user_id, dimension_key)


@router.patch("/{dimension_key}", response_model=AbilityDimensionOut)
async def patch_dimension(
    dimension_key: str,
    body: PatchAbilityDimensionInput,
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityService = Depends(_get_service),
) -> dict:
    return await svc.patch(user_id, dimension_key, body.model_dump(exclude_none=True))


@router.post("/{dimension_key}/toggle", response_model=AbilityDimensionOut)
async def toggle_dimension(
    dimension_key: str,
    body: ToggleDimensionInput = ToggleDimensionInput(),
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityService = Depends(_get_service),
) -> dict:
    return await svc.toggle(user_id, dimension_key, body.is_active)


__all__ = ["router"]
