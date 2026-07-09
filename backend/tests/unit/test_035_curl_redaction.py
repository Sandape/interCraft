from __future__ import annotations

from app.modules.agent_observability.curl import build_safe_curl


def test_build_safe_curl_replaces_secret_headers_with_placeholders() -> None:
    result = build_safe_curl(
        method="POST",
        base_url="https://api.example.com",
        endpoint="/v1/chat/completions",
        headers={
            "Authorization": "Bearer sk-live-secret",
            "Cookie": "sid=secret",
            "Content-Type": "application/json",
            "X-Request-ID": "req_123",
        },
        body={"model": "deepseek-v4-pro", "messages": "[REDACTED]"},
        provider="openai-compatible",
        model="deepseek-v4-pro",
        trace_id="trace_123",
        attempt=2,
    )

    assert "sk-live-secret" not in result.curl
    assert "sid=secret" not in result.curl
    assert "Authorization: Bearer $PROVIDER_API_KEY" in result.curl
    assert "Cookie" not in result.curl
    assert "trace_123" in result.curl
    assert result.redacted_headers == ["Authorization", "Cookie"]


def test_build_safe_curl_redacts_secret_body_fields_recursively() -> None:
    result = build_safe_curl(
        method="POST",
        base_url="https://api.example.com",
        endpoint="/v1/responses",
        headers={"Content-Type": "application/json"},
        body={
            "model": "deepseek-v4-pro",
            "api_key": "sk-body-secret",
            "nested": {"refresh_token": "refresh-secret"},
        },
        provider="openai-compatible",
        model="deepseek-v4-pro",
        trace_id="trace_123",
        attempt=1,
    )

    assert "sk-body-secret" not in result.curl
    assert "refresh-secret" not in result.curl
    assert "[REDACTED_SECRET]" in result.curl
