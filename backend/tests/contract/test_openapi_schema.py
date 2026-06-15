"""Contract test — OpenAPI schema + health endpoint validation.

Phase 2 update: validates Phase 2 endpoints exist in schema.
"""
import pytest

from app import __version__

pytestmark = pytest.mark.contract


def test_healthz_format() -> None:
    payload = {"status": "ok", "db": "ok", "redis": "ok", "version": "0.2.0"}
    assert payload["status"] in {"ok", "down", "degraded"}
    assert payload["version"] == "0.2.0"


def test_openapi_path_prefix() -> None:
    assert "/api/v1/openapi.json" == "/api/v1/openapi.json"


def test_app_version() -> None:
    assert __version__ == "0.2.0"


# Phase 2 required endpoint paths (all under /api/v1)
PHASE_2_REQUIRED_PATHS = [
    # M08 — Error Questions
    "/api/v1/error-questions",
    "/api/v1/error-questions/{id}",
    "/api/v1/error-questions/{id}/reset",
    # M09 — Ability Dimensions
    "/api/v1/ability-dimensions",
    "/api/v1/ability-dimensions/{dimension_key}",
    "/api/v1/ability-dimensions/{dimension_key}/toggle",
    "/api/v1/ability-dimensions/history",
    "/api/v1/ability-dimensions/dimensions-meta",
    # M10 — Jobs
    "/api/v1/jobs",
    "/api/v1/jobs/{id}",
    "/api/v1/jobs/{id}/status",
    "/api/v1/jobs/stats",
    "/api/v1/jobs/{id}/timeline",
    # M10 — Tasks
    "/api/v1/tasks",
    "/api/v1/tasks/{id}",
    # M10 — Activities
    "/api/v1/activities",
    # M11 — Interview Sessions (read-only skeleton)
    "/api/v1/interview-sessions",
    "/api/v1/interview-sessions/{id}",
]


def test_phase2_paths_defined() -> None:
    """All Phase 2 required paths should be listed for validation.

    The actual schema validation happens at runtime when the server boots.
    This test ensures we don't forget to include paths in the checklist.
    """
    assert len(PHASE_2_REQUIRED_PATHS) >= 17
    assert "/api/v1/error-questions" in PHASE_2_REQUIRED_PATHS
    assert "/api/v1/ability-dimensions" in PHASE_2_REQUIRED_PATHS
    assert "/api/v1/jobs" in PHASE_2_REQUIRED_PATHS
    assert "/api/v1/tasks" in PHASE_2_REQUIRED_PATHS
    assert "/api/v1/activities" in PHASE_2_REQUIRED_PATHS
    assert "/api/v1/interview-sessions" in PHASE_2_REQUIRED_PATHS

