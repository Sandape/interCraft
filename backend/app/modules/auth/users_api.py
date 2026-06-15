"""Profile API — mounted at /api/v1/users/*."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.modules.auth.schemas import PatchUserInput, PublicUser
from app.modules.auth.service import AuthService

router = APIRouter()


@router.get("/me", response_model=PublicUser)
async def get_me(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    return await AuthService(db).get_me(user_id)


@router.patch("/me", response_model=PublicUser)
async def patch_me(
    payload: PatchUserInput,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    return await AuthService(db).patch_me(user_id, **payload.model_dump(exclude_unset=True))
