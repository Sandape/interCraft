"""REQ-039 B1 — admin_observability OpenAPI contract test.

Locks the 7-endpoint surface + payload shapes documented in
``specs/039-log-center-full/spec.md`` + ``.claude/teams/req039/ac-matrix``:

- ``GET /api/v1/admin-console/observability/health`` (placeholder)
- ``GET /api/v1/admin-console/observability/tasks/{task_id}/tags``
- ``POST /api/v1/admin-console/observability/tasks/{task_id}/tags``
- ``DELETE /api/v1/admin-console/observability/tasks/{task_id}/tags``
- ``POST /api/v1/admin-console/observability/traces/{trace_id}/replay``
- ``POST /api/v1/admin-console/observability/traces/diff``
- ``GET /api/v1/admin-console/observability/traces/{trace_id}/nodes/{node_id}/payload``

The contract test does NOT need a real DB — it only introspects the
FastAPI OpenAPI schema. Skipped if ``DATABASE_URL`` is not configured
for parity with the rest of the 033/039 suites.
"""
from __future__ import annotations

import os

import pytest


@pytest.mark.contract
def test_admin_observability_routes_in_openapi() -> None:
    """All 7 routes + the canonical paths must appear in OpenAPI."""
    from app.main import create_app

    app = create_app()
    paths = {
        "/api/v1/admin-console/observability/health",
        "/api/v1/admin-console/observability/tasks/{task_id}/tags",
        "/api/v1/admin-console/observability/traces/{trace_id}/replay",
        "/api/v1/admin-console/observability/traces/diff",
        "/api/v1/admin-console/observability/traces/{trace_id}/nodes/{node_id}/payload",
    }
    actual = {
        r.path
        for r in app.routes
        if hasattr(r, "path") and "/admin-console/observability" in r.path
    }
    missing = paths - actual
    assert not missing, f"missing admin_observability routes: {missing}"


@pytest.mark.contract
def test_tag_post_response_schema_present() -> None:
    """The POST /tags response must declare a 201 + 409 + 422 + 403 envelope."""
    from app.main import create_app

    app = create_app()
    schema = app.openapi()
    post = schema["paths"]["/api/v1/admin-console/observability/tasks/{task_id}/tags"]["post"]
    assert "201" in post["responses"]
    assert "409" in post["responses"]
    assert "422" in post["responses"]
    assert "403" in post["responses"]


@pytest.mark.contract
def test_replay_response_schema_present() -> None:
    """Replay POST must declare 201 + 404 + 410 + 429."""
    from app.main import create_app

    app = create_app()
    schema = app.openapi()
    post = schema["paths"]["/api/v1/admin-console/observability/traces/{trace_id}/replay"]["post"]
    for status_code in ("201", "403", "404", "410", "429"):
        assert status_code in post["responses"], f"missing status {status_code}"


@pytest.mark.contract
def test_diff_response_schema_present() -> None:
    """Diff POST must declare 200 + 400 + 404 + 429."""
    from app.main import create_app

    app = create_app()
    schema = app.openapi()
    post = schema["paths"]["/api/v1/admin-console/observability/traces/diff"]["post"]
    for status_code in ("200", "400", "404", "429"):
        assert status_code in post["responses"], f"missing status {status_code}"


@pytest.mark.contract
def test_payload_endpoint_response_schema_present() -> None:
    """GET payload must declare 200 + 404 + 413."""
    from app.main import create_app

    app = create_app()
    schema = app.openapi()
    get = schema["paths"]["/api/v1/admin-console/observability/traces/{trace_id}/nodes/{node_id}/payload"]["get"]
    for status_code in ("200", "404", "413"):
        assert status_code in get["responses"], f"missing status {status_code}"


@pytest.mark.contract
def test_tag_create_schema_in_openapi() -> None:
    """TaskTagCreateRequest schema must be registered with the 50-char length bound."""
    from app.main import create_app

    app = create_app()
    schema = app.openapi()
    # Pydantic v2 inlines request body schemas; we verify the operation
    # references the schema and the model has a 50-char max_length bound.
    post = schema["paths"]["/api/v1/admin-console/observability/tasks/{task_id}/tags"]["post"]
    body_ref = post["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    schema_name = body_ref.rsplit("/", 1)[-1]
    assert schema_name == "TaskTagCreateRequest"
    model_schema = schema["components"]["schemas"]["TaskTagCreateRequest"]
    # ``tag`` is the field; length constraint surfaces as maxLength.
    assert model_schema["properties"]["tag"]["maxLength"] == 50
    assert model_schema["properties"]["tag"]["minLength"] == 1


@pytest.mark.contract
def test_no_polling_in_admin_observability_module() -> None:
    """FR-005 / E7 — code-review check that no setInterval /
    refetchInterval / EventSource landed in the backend log-center code.

    Note: this guard is for the FRONTEND per spec, but we lock the
    backend too as defense-in-depth (the API layer must never add a
    background job that polls a trace status).
    """
    from pathlib import Path

    module_dir = Path(__file__).resolve().parents[2] / "app" / "modules" / "admin_console"
    files = list(module_dir.rglob("*.py"))
    forbidden = ("setInterval(", "refetchInterval", "EventSource")
    offenders: list[str] = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                offenders.append(f"{f}:{needle}")
    assert not offenders, f"forbidden polling primitives found: {offenders}"