"""Auth API routes — only register / login / refresh / logout / oauth placeholder.

Profile (`/users/me`) lives in `app/modules/auth/users_api.py` so the
v1 router can mount it under `/users`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.core.exceptions import AppError, TokenMissingError
from app.core.metrics import auth_register_attempts_total
from app.core.rate_limit import enforce_rate_limit
from app.modules.auth.schemas import (
    AuthLoginResponse,
    AuthRegisterResponse,
    LoginInput,
    RefreshRequest,
    RefreshResponse,
    RegisterInput,
)
from app.modules.auth.service import AuthService

router = APIRouter()


async def _client_meta(request: Request) -> tuple[str | None, str | None]:
    fwd = request.headers.get("x-forwarded-for")
    ip = (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None))
    ua = request.headers.get("user-agent")
    return ip, ua


@router.post(
    "/register",
    response_model=AuthRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterInput,
    request: Request,
    db: AsyncSession = Depends(db_session_user_dep),
):
    await enforce_rate_limit(request, scope="auth")
    ip, ua = await _client_meta(request)
    service = AuthService(db)
    try:
        user, tokens = await service.register(payload, ip=ip, ua=ua)
    except AppError:
        auth_register_attempts_total.labels(result="failed").inc()
        raise
    auth_register_attempts_total.labels(result="success").inc()
    return AuthRegisterResponse(user=user, tokens=tokens)


@router.post("/login", response_model=AuthLoginResponse)
async def login(
    payload: LoginInput,
    request: Request,
    db: AsyncSession = Depends(db_session_user_dep),
):
    await enforce_rate_limit(request, scope="auth")
    ip, ua = await _client_meta(request)
    service = AuthService(db)
    user, tokens, evicted = await service.login(payload, ip=ip, ua=ua)
    return AuthLoginResponse(user=user, tokens=tokens, evicted_session_id=evicted)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    payload: RefreshRequest,
    request: Request,
    refresh_token_hdr: str | None = Header(default=None, alias="Refresh-Token"),
    db: AsyncSession = Depends(db_session_user_dep),
):
    await enforce_rate_limit(request, scope="auth")
    token = payload.refresh_token or refresh_token_hdr
    if not token:
        raise TokenMissingError()
    service = AuthService(db)
    tokens = await service.refresh(token)
    return RefreshResponse(tokens=tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    user_id=Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    from uuid import UUID

    sid = getattr(request.state, "session_id", None)
    if not sid:
        raise TokenMissingError()
    service = AuthService(db)
    await service.logout(UUID(sid))
    return None


# OAuth placeholder (Phase 1: 501). Per spec OOS-6.
@router.post("/oauth/{provider}/callback")
async def oauth_callback(provider: str):
    raise AppError(
        "not_implemented",
        f"OAuth '{provider}' will be available in v1.1",
        http_status=501,
    )
