"""Structured logging setup (structlog)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.tracebacks import ExceptionDictTransformer

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
        "api_key",
        "auth_token",
        "bot_token",
        "client_secret",
        "context_token",
        "cookie",
        "database_url",
        "dsn",
        "jd_text",
        "jwt_secret",
        "master_key",
        "message_content",
        "password",
        "provider_api_key",
        "prompt",
        "provider_body",
        "qrcode_token",
        "raw_message",
        "reasoning_content",
        "refresh_token",
        "access_token",
        "redis_url",
        "resume_body",
        "system_prompt",
        "session_token",
        "tavily_api_key",
        "token",
        "tool_args",
        "tool_result",
    }
)
_PRIVATE_ID_LOG_KEYS = frozenset(
    {"from_user_id", "owner_id", "to_user_id", "user_id", "wechat_uin"}
)
_CAMEL_CASE_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_KEY_CHARACTER = re.compile(r"[^a-z0-9]+")
_SENSITIVE_LOG_KEY_SUFFIXES = (
    "_access_token",
    "_api_key",
    "_auth_token",
    "_client_secret",
    "_cookie",
    "_password",
    "_refresh_token",
    "_secret",
    "_session_token",
)
_SECRET_LOG_VALUE = re.compile(
    r"(?i)("
    r"(?:postgres(?:ql)?(?:\+[a-z0-9_]+)?|rediss?|https?)://"
    r"[^\s/:@]+:[^\s/@]+@|"
    r"['\"]?(?:authorization|(?:[a-z0-9]+[_-])*(?:api[_-]?key|"
    r"auth[_-]?token|access[_-]?token|refresh[_-]?token|session[_-]?token|"
    r"client[_-]?secret|password|passwd|cookie|token|secret))['\"]?\s*[:=]|"
    r"bearer\s+|"
    r"\b(?:sk|tvly|tavily|ghp|github_pat|xox[baprs])[-_][a-z0-9_-]{8,}|"
    r"\beyj[a-z0-9_-]{6,}\.[a-z0-9_-]{6,}\.[a-z0-9_-]{6,}\b|"
    r"(?:password|passwd|cookie|access[_-]?token|refresh[_-]?token|"
    r"session[_-]?token|api[_-]?key|client[_-]?secret)\s*[:=]"
    r")"
)
_EMAIL_VALUE = re.compile(r"(?i)(?<![\w.+-])[\w.+-]+@[\w.-]+\.[a-z]{2,}(?![\w.-])")
_CN_PHONE_VALUE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")


def _canonical_log_key(key: Any) -> str:
    with_boundaries = _CAMEL_CASE_BOUNDARY.sub("_", str(key).strip())
    return _NON_KEY_CHARACTER.sub("_", with_boundaries.lower()).strip("_")


def _is_sensitive_log_key(key: Any) -> bool:
    canonical = _canonical_log_key(key)
    return (
        canonical in _SENSITIVE_LOG_KEYS
        or canonical.endswith("_authorization")
        or canonical.endswith(_SENSITIVE_LOG_KEY_SUFFIXES)
    )


def _scrub_log_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***REDACTED***"
            if _is_sensitive_log_key(key)
            else hashlib.sha256(str(item).encode()).hexdigest()[:24]
            if _canonical_log_key(key) in _PRIVATE_ID_LOG_KEYS and item is not None
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
    """Render a safe exception summary for legacy stdlib log records."""

    @staticmethod
    def _exception_summary(record: logging.LogRecord) -> dict[str, Any] | None:
        if not record.exc_info:
            return None
        exc_type, exc, traceback = record.exc_info
        while traceback is not None and traceback.tb_next is not None:
            traceback = traceback.tb_next
        summary: dict[str, Any] = {
            "type": getattr(exc_type, "__name__", "Exception"),
            "message": _scrub_log_value(str(exc)),
        }
        if traceback is not None:
            code = traceback.tb_frame.f_code
            summary.update(
                {
                    "file": os.path.basename(code.co_filename),
                    "function": code.co_name,
                    "line": traceback.tb_lineno,
                }
            )
        return summary

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "_intercraft_redacted", False):
            return True
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = f"{record.name}.log_format_error"
        rendered = _scrub_log_value(rendered)
        exception = self._exception_summary(record)
        record.safe_message = rendered
        record.safe_exception = exception
        if exception is None:
            record.msg = rendered
        else:
            record.msg = (
                f"{rendered} exception="
                f"{json.dumps(exception, ensure_ascii=True, sort_keys=True, separators=(',', ':'))}"
            )
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record._intercraft_redacted = True
        return True


class _StructuredStdlibFormatter(logging.Formatter):
    """Emit legacy stdlib records as valid, redacted JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "event": f"{record.name}.{record.levelname}",
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": getattr(record, "safe_message", record.getMessage()),
        }
        exception = getattr(record, "safe_exception", None)
        if exception is not None:
            payload["exception"] = exception
        request_id = _request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        return json.dumps(
            _scrub_log_value(payload),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )


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
        processors.append(
            structlog.processors.ExceptionRenderer(ExceptionDictTransformer(show_locals=False))
        )
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
        _stderr.setFormatter(_StructuredStdlibFormatter())
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
