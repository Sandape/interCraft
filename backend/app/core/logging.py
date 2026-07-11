"""Structured logging setup (structlog)."""

from __future__ import annotations

import hashlib
import logging
import re
import sys
from contextvars import ContextVar
from typing import Any

import structlog

from app.core.config import get_settings
from app.observability.tracing import _inject_otel_context

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


_SENSITIVE_LOG_KEYS = frozenset(
    {
        "authorization",
        "bot_token",
        "context_token",
        "cookie",
        "jd_text",
        "jwt_secret",
        "master_key",
        "message_content",
        "password",
        "prompt",
        "provider_body",
        "qrcode_token",
        "raw_message",
        "reasoning_content",
        "refresh_token",
        "access_token",
        "resume_body",
        "system_prompt",
        "tool_args",
        "tool_result",
    }
)
_PRIVATE_ID_LOG_KEYS = frozenset(
    {"from_user_id", "owner_id", "to_user_id", "user_id", "wechat_uin"}
)
_SECRET_LOG_VALUE = re.compile(
    r"(?i)(authorization\s*:|bearer\s+|\bsk-[a-z0-9_-]+|"
    r"password\s*=|cookie\s*=|api[_-]?key\s*=)"
)
_EMAIL_VALUE = re.compile(r"(?i)(?<![\w.+-])[\w.+-]+@[\w.-]+\.[a-z]{2,}(?![\w.-])")
_CN_PHONE_VALUE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")


def _scrub_log_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***REDACTED***"
            if str(key).strip().lower() in _SENSITIVE_LOG_KEYS
            else hashlib.sha256(str(item).encode()).hexdigest()[:24]
            if str(key).strip().lower() in _PRIVATE_ID_LOG_KEYS and item is not None
            else _scrub_log_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_scrub_log_value(item) for item in value]
    if isinstance(value, str):
        if _SECRET_LOG_VALUE.search(value):
            return "***REDACTED***"
        return _CN_PHONE_VALUE.sub(
            "***PHONE_REDACTED***",
            _EMAIL_VALUE.sub("***EMAIL_REDACTED***", value[:2000]),
        )
    return value


def _drop_sensitive(_: Any, __: str, event_dict: dict) -> dict:
    """Recursively scrub credentials, business text and common PII."""
    return _scrub_log_value(event_dict)


class _RedactingStdlibFilter(logging.Filter):
    """Keep legacy stdlib logs useful without rendering exception bodies."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = f"{record.name}.log_format_error"
        record.msg = _scrub_log_value(rendered)
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        return True


def configure_logging() -> None:
    """Initialise structlog + stdlib logging bridge.

    Idempotent: calling twice is safe (mostly used by tests).
    """
    settings = get_settings()
    is_dev = settings.app_env != "production"

    processors: list = [
        structlog.contextvars.merge_contextvars,
        _inject_context,
        _inject_otel_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if is_dev:
        processors.append(structlog.processors.format_exc_info)
        processors.append(_drop_sensitive)
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.dict_tracebacks)
        processors.append(_drop_sensitive)
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

    # Bridge stdlib logging → same stderr sink. Modules that still use
    # ``logging.getLogger(__name__)`` (e.g. app.channels.ilink_pool) would
    # otherwise have no handler at all and their INFO/ERROR output is silently
    # dropped. Keep the stdlib format minimal so it doesn't fight structlog's
    # JSON renderer; just emit ``level name message`` on one line.
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        _stderr = logging.StreamHandler(sys.stderr)
        _stderr.setFormatter(
            logging.Formatter(
                fmt='{"event": "%(name)s.%(levelname)s", "level": "%(levelname)s", '
                '"logger": "%(name)s", "message": %(message)r}\n',
            )
        )
        root_logger.addHandler(_stderr)
    for handler in root_logger.handlers:
        if not any(isinstance(item, _RedactingStdlibFilter) for item in handler.filters):
            handler.addFilter(_RedactingStdlibFilter())
    root_logger.setLevel(getattr(logging, settings.log_level, logging.INFO))

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
