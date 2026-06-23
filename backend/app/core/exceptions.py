"""Unified application exception types and FastAPI handlers.

Renders the shared `events.md` error envelope on all raised errors.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.agents.exceptions import CheckpointerUnavailableError


class AppError(Exception):
    """Base class for all app-raised, structured errors.

    Handlers render these as `{ "error": { "code", "message", "details?", "request_id" } }`.
    """

    http_status: int = 400
    code: str = "app.error"
    message: str = "Application error"

    def __init__(
        self,
        code: str | None = None,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message or self.message)
        self.message_override = message
        self.details = details
        self.code_override = code
        self.http_status_override = http_status


class AuthError(AppError):
    http_status = 401
    code = "auth.unauthenticated"
    message = "Authentication required"


class TokenInvalidError(AuthError):
    code = "auth.token_invalid"
    message = "Invalid or expired token"


class TokenMissingError(AuthError):
    code = "auth.token_missing"
    message = "Missing Authorization header"


class RefreshInvalidError(AuthError):
    code = "auth.refresh_invalid"
    message = "Refresh token invalid, expired, or revoked"


class NotFoundError(AppError):
    http_status = 404
    code = "resource.not_found"
    message = "Resource not found"


class ValidationError(AppError):
    http_status = 422
    code = "validation.failed"
    message = "Request payload invalid"


class EmailTakenError(AppError):
    http_status = 409
    code = "auth.email_taken"
    message = "Email already registered"


class PasswordTooWeakError(ValidationError):
    code = "auth.password_too_weak"
    message = "Password does not meet strength policy"


class RateLimitError(AppError):
    http_status = 429
    code = "rate_limit.exceeded"
    message = "Too many requests"


class SessionOtherUserError(AppError):
    http_status = 403
    code = "auth.session_other_user"
    message = "Cannot modify another user's session"


class VersionRestoreDepthExceededError(AppError):
    http_status = 500
    code = "version.restore_depth_exceeded"
    message = "Version diff chain too deep (>100)"


# ---- Handlers ----


def _envelope(
    *,
    code: str,
    message: str,
    request_id: str | None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message, "request_id": request_id or str(uuid.uuid4())}
    if details:
        err["details"] = details
    return {"error": err}


def _rid(request: Request) -> str:
    return (
        request.headers.get("X-Request-ID")
        or getattr(request.state, "request_id", None)
        or str(uuid.uuid4())
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CheckpointerUnavailableError)
    async def _checkpointer_unavailable(request: Request, exc: CheckpointerUnavailableError) -> JSONResponse:
        rid = _rid(request)
        return JSONResponse(
            status_code=503,
            content=_envelope(
                code="agent.checkpointer_unavailable",
                message="面试服务暂时不可用，请稍后重试",
                request_id=rid,
                details={"retry_after": exc.retry_after},
            ),
            headers={"X-Request-ID": rid, "Retry-After": str(exc.retry_after)},
        )

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        code = exc.code_override or exc.code
        msg = exc.message_override or exc.message
        status = exc.http_status_override or exc.http_status
        rid = _rid(request)
        body = _envelope(code=code, message=msg, request_id=rid, details=exc.details)
        return JSONResponse(status_code=status, content=body, headers={"X-Request-ID": rid})

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        field_errors: list[dict[str, Any]] = []
        for e in exc.errors():
            field_errors.append(
                {
                    "field": ".".join(str(p) for p in e.get("loc", [])),
                    "code": e.get("type", "validation"),
                    "message": e.get("msg", ""),
                }
            )
        rid = _rid(request)
        return JSONResponse(
            status_code=422,
            content=_envelope(
                code="validation.failed",
                message="Request validation failed",
                request_id=rid,
                details={"field_errors": field_errors},
            ),
            headers={"X-Request-ID": rid},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        rid = _rid(request)
        # 024 FIX: when callers raise HTTPException(detail={"error": {...}}),
        # preserve the inner code/message/details instead of flattening to
        # `http.<status>`. This keeps backwards compatibility with handlers
        # that built the structured envelope directly (e.g. errors service
        # `source_already_cleared`).
        detail = exc.detail
        if isinstance(detail, dict) and isinstance(detail.get("error"), dict):
            inner = detail["error"]
            return JSONResponse(
                status_code=exc.status_code,
                content=_envelope(
                    code=inner.get("code", f"http.{exc.status_code}"),
                    message=inner.get("message", "HTTP error"),
                    request_id=rid,
                    details=inner.get("details"),
                ),
                headers={"X-Request-ID": rid},
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(
                code=f"http.{exc.status_code}",
                message=str(exc.detail) if exc.detail else "HTTP error",
                request_id=rid,
            ),
            headers={"X-Request-ID": rid},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        from app.core.logging import get_logger

        rid = _rid(request)
        get_logger("errors").exception(
            "unhandled.exception", request_id=rid, error_type=type(exc).__name__
        )
        return JSONResponse(
            status_code=500,
            content=_envelope(
                code="internal.error",
                message="Internal server error",
                request_id=rid,
            ),
            headers={"X-Request-ID": rid},
        )


__all__ = [
    "AppError",
    "AuthError",
    "EmailTakenError",
    "NotFoundError",
    "PasswordTooWeakError",
    "RateLimitError",
    "RefreshInvalidError",
    "SessionOtherUserError",
    "TokenInvalidError",
    "TokenMissingError",
    "ValidationError",
    "VersionRestoreDepthExceededError",
    "install_exception_handlers",
]
