"""Security regression tests for production exception log redaction."""

from __future__ import annotations

import io
import json
import logging
from contextlib import redirect_stderr
from types import SimpleNamespace

import structlog

import app.core.logging as logging_module

_SYNTHETIC_SECRETS = (
    "synthetic-db-password",
    "synthetic-redis-password",
    "synthetic-http-password",
    "sk-synthetic-provider-key-123456789",
    "eyJzeW50aGV0aWMiOiJ0cnVlIn0.c3ludGhldGljLXBheWxvYWQ.c3ludGhldGljLXNpZw",
    "synthetic-cookie-secret",
    "synthetic-token-secret",
    "synthetic-plain-password",
)


def _raise_with_secret_locals() -> None:
    postgres_url = "postgresql+asyncpg://svc:synthetic-db-password@db.test/app"
    redis_url = "redis://cache:synthetic-redis-password@redis.test/0"
    basic_auth_url = "https://api:synthetic-http-password@example.test/path"
    provider_key = "sk-synthetic-provider-key-123456789"
    jwt = _SYNTHETIC_SECRETS[4]
    cookie = "session=synthetic-cookie-secret"
    access_token = "synthetic-token-secret"
    password = "synthetic-plain-password"
    assert all(
        (postgres_url, redis_url, basic_auth_url, provider_key, jwt, cookie, access_token, password)
    )
    raise RuntimeError(f"dependency failed for {redis_url}")


def _render_production_exception(monkeypatch) -> dict:
    stream = io.StringIO()

    def inject_trace(_: object, __: str, event: dict) -> dict:
        event["trace_id"] = "trace-safe-123"
        event["span_id"] = "span-safe-456"
        return event

    monkeypatch.setattr(
        logging_module,
        "get_settings",
        lambda: SimpleNamespace(app_env="production", log_level="INFO"),
    )
    monkeypatch.setattr(logging_module, "_inject_otel_context", inject_trace)
    logging_module.bind_request_context("request-safe-789", "user-safe-123")
    try:
        with redirect_stderr(stream):
            logging_module.configure_logging()
            try:
                _raise_with_secret_locals()
            except RuntimeError:
                logging_module.get_logger("redaction-test").error(
                    "dependency.failed",
                    exc_info=True,
                    elapsed_ms=17,
                )
    finally:
        logging_module.clear_request_context()
        structlog.reset_defaults()
    return json.loads(stream.getvalue().strip().splitlines()[-1])


def test_production_exception_chain_drops_locals_and_retains_diagnostics(monkeypatch) -> None:
    payload = _render_production_exception(monkeypatch)
    rendered = json.dumps(payload, ensure_ascii=True)

    for secret in _SYNTHETIC_SECRETS:
        assert secret not in rendered
    assert "postgresql+asyncpg://svc:" not in rendered
    assert "redis://cache:" not in rendered
    assert "https://api:" not in rendered

    assert payload["event"] == "dependency.failed"
    assert payload["level"] == "error"
    assert payload["request_id"] == "request-safe-789"
    assert payload["trace_id"] == "trace-safe-123"
    assert payload["span_id"] == "span-safe-456"
    assert payload["elapsed_ms"] == 17
    assert payload["timestamp"]

    exception = payload["exception"][0]
    assert exception["exc_type"] == "RuntimeError"
    assert exception["exc_value"] == "***REDACTED***"
    frame = exception["frames"][-1]
    assert frame["filename"].endswith("test_core_logging_redaction.py")
    assert frame["name"] == "_raise_with_secret_locals"
    assert isinstance(frame["lineno"], int)
    assert "locals" not in frame


def test_recursive_scrubber_redacts_credential_values() -> None:
    event = {
        "database_url": "postgresql://svc:synthetic-db-password@db.test/app",
        "nested": [
            "https://api:synthetic-http-password@example.test/path",
            {"provider": "sk-synthetic-provider-key-123456789"},
            {"jwt": _SYNTHETIC_SECRETS[4]},
        ],
        "access_token": "synthetic-token-secret",
        "headers": {"X-API-Key": "synthetic-random-api-secret"},
        "apiKey": "synthetic-camel-api-secret",
        "deepseek_api_key": "synthetic-provider-api-secret",
        "auth_token": "synthetic-random-token-secret",
        "token_count": 42,
        "authorization_status": "valid",
    }

    scrubbed = logging_module._scrub_log_value(event)
    rendered = json.dumps(scrubbed)
    for secret in _SYNTHETIC_SECRETS:
        assert secret not in rendered
    for secret in (
        "synthetic-random-api-secret",
        "synthetic-camel-api-secret",
        "synthetic-provider-api-secret",
        "synthetic-random-token-secret",
    ):
        assert secret not in rendered
    assert scrubbed["token_count"] == 42
    assert scrubbed["authorization_status"] == "valid"


def test_string_scrubber_handles_quoted_secret_keys_and_basic_auth() -> None:
    values = (
        'provider failed: {"api_key":"synthetic-random-api-secret"}',
        'headers={"Authorization":"Basic c3ludGhldGljOnNlY3JldA=="}',
        "apiKey=synthetic-camel-api-secret",
        "deepseek_api_key=synthetic-provider-api-secret",
        "auth_token=synthetic-random-token-secret",
    )

    assert [logging_module._scrub_log_value(value) for value in values] == ["***REDACTED***"] * len(
        values
    )
    assert logging_module._scrub_log_value("token_count=42") == "token_count=42"


def test_configured_stdlib_bridge_emits_safe_valid_json(monkeypatch) -> None:
    stream = io.StringIO()
    root_logger = logging.getLogger()
    previous_handlers = list(root_logger.handlers)
    previous_level = root_logger.level
    root_logger.handlers.clear()
    monkeypatch.setattr(
        logging_module,
        "get_settings",
        lambda: SimpleNamespace(app_env="production", log_level="INFO"),
    )
    logging_module.bind_request_context("request-stdlib-safe", None)
    try:
        with redirect_stderr(stream):
            logging_module.configure_logging()
            try:
                _raise_with_secret_locals()
            except RuntimeError:
                logging.getLogger("stdlib-redaction-test").exception("dependency failed")
    finally:
        root_logger.handlers.clear()
        root_logger.handlers.extend(previous_handlers)
        root_logger.setLevel(previous_level)
        logging_module.clear_request_context()
        structlog.reset_defaults()

    payload = json.loads(stream.getvalue().strip().splitlines()[-1])
    rendered = json.dumps(payload)
    for secret in _SYNTHETIC_SECRETS:
        assert secret not in rendered
    assert payload["event"] == "stdlib-redaction-test.ERROR"
    assert payload["level"] == "error"
    assert payload["message"] == "dependency failed"
    assert payload["request_id"] == "request-stdlib-safe"
    assert payload["exception"]["type"] == "RuntimeError"
    assert payload["exception"]["message"] == "***REDACTED***"
    assert payload["exception"]["function"] == "_raise_with_secret_locals"
    assert payload["exception"]["file"] == "test_core_logging_redaction.py"
    assert isinstance(payload["exception"]["line"], int)


def test_existing_stdlib_handlers_keep_formatters_and_share_safe_summary(monkeypatch) -> None:
    streams = (io.StringIO(), io.StringIO())
    handlers = [logging.StreamHandler(stream) for stream in streams]
    formatters = [
        logging.Formatter("FIRST:%(message)s"),
        logging.Formatter("SECOND:%(message)s"),
    ]
    for handler, formatter in zip(handlers, formatters, strict=True):
        handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    previous_handlers = list(root_logger.handlers)
    previous_level = root_logger.level
    root_logger.handlers.clear()
    root_logger.handlers.extend(handlers)
    monkeypatch.setattr(
        logging_module,
        "get_settings",
        lambda: SimpleNamespace(app_env="production", log_level="INFO"),
    )
    try:
        logging_module.configure_logging()
        try:
            _raise_with_secret_locals()
        except RuntimeError:
            logging.getLogger("stdlib-multi-handler").exception("dependency failed")
    finally:
        root_logger.handlers.clear()
        root_logger.handlers.extend(previous_handlers)
        root_logger.setLevel(previous_level)
        structlog.reset_defaults()

    assert [handler.formatter for handler in handlers] == formatters
    outputs = [stream.getvalue() for stream in streams]
    assert outputs[0].startswith("FIRST:dependency failed")
    assert outputs[1].startswith("SECOND:dependency failed")
    for output in outputs:
        for secret in _SYNTHETIC_SECRETS:
            assert secret not in output
        assert '"type":"RuntimeError"' in output
        assert '"message":"***REDACTED***"' in output
        assert '"function":"_raise_with_secret_locals"' in output
