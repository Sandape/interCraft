"""Structured logging setup (structlog)."""
from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

from app.core.config import get_settings

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def bind_request_context(request_id: str | None = None, user_id: str | None = None) -> None:
    if request_id is not None:
        _request_id_var.set(request_id)
    if user_id is not None:
        _user_id_var.set(user_id)


def clear_request_context() -> None:
    _request_id_var.set(None)
    _user_id_var.set(None)


def _inject_context(_: Any, __: str, event_dict: dict) -> dict:
    rid = _request_id_var.get()
    uid = _user_id_var.get()
    if rid:
        event_dict["request_id"] = rid
    if uid:
        event_dict["user_id"] = uid
    return event_dict


def _drop_sensitive(_: Any, __: str, event_dict: dict) -> dict:
    """Scrub known-sensitive keys from log payloads."""
    sensitive = {"password", "refresh_token", "access_token", "master_key", "jwt_secret"}
    for k in list(event_dict.keys()):
        if k.lower() in sensitive:
            event_dict[k] = "***REDACTED***"
    return event_dict


def configure_logging() -> None:
    """Initialise structlog + stdlib logging bridge.

    Idempotent: calling twice is safe (mostly used by tests).
    """
    settings = get_settings()
    is_dev = settings.app_env != "production"

    processors: list = [
        structlog.contextvars.merge_contextvars,
        _inject_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _drop_sensitive,
    ]
    if is_dev:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.dict_tracebacks)
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level, logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Quiet down noisy loggers.
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str = "intercraft") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


__all__ = [
    "bind_request_context",
    "clear_request_context",
    "configure_logging",
    "get_logger",
]
