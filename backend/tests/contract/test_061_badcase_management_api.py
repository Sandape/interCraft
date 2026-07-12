"""REQ-061 T125 — OpenAPI contract tests for Bad Case management API."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

OPENAPI_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "061-ai-agent-production"
    / "contracts"
    / "ai-operations.openapi.yaml"
)

BADCASE_PATHS = {
    "/badcases",
    "/badcases/{badcaseId}",
    "/badcases/{badcaseId}/timeline",
    "/badcases/{badcaseId}/impacts",
    "/badcases/{badcaseId}/actions",
}

REQUIRED_SUMMARY = {
    "badcase_id",
    "status",
    "severity",
    "category",
    "capabilities",
    "owner",
    "privacy_class",
    "first_seen_at",
    "last_seen_at",
    "task_count",
    "user_count_status",
    "point_treatment_status",
    "sla_status",
    "version",
    "data_completeness",
}

ACTION_TYPES = {
    "CLASSIFY",
    "ASSIGN",
    "MERGE",
    "ADD_NOTE",
    "ESCALATE_INCIDENT",
    "RECORD_POINT_TREATMENT",
    "PROMOTE_REGRESSION",
    "MARK_UNREPRODUCIBLE",
    "CLOSE",
    "INTAKE",
}


def _spec() -> dict:
    return yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))


def test_openapi_declares_badcase_management_paths() -> None:
    paths = set(_spec()["paths"])
    assert BADCASE_PATHS <= paths


def test_openapi_badcase_list_supports_cursor_filters() -> None:
    params = {
        p["name"] for p in _spec()["paths"]["/badcases"]["get"]["parameters"]
    }
    for name in (
        "status",
        "severity",
        "category",
        "capability",
        "owner",
        "source",
        "privacy_class",
        "point_treatment_status",
        "sla_status",
        "cursor",
        "limit",
    ):
        assert name in params


def test_openapi_actions_require_idempotency_and_discriminator() -> None:
    post = _spec()["paths"]["/badcases/{badcaseId}/actions"]["post"]
    param_names: set[str] = set()
    for p in post.get("parameters", []):
        if "name" in p:
            param_names.add(p["name"])
        elif "$ref" in p:
            ref = p["$ref"].split("/")[-1]
            resolved = _spec()["components"]["parameters"].get(ref, {})
            if "name" in resolved:
                param_names.add(resolved["name"])
    assert "Idempotency-Key" in param_names
    schema = post["requestBody"]["content"]["application/json"]["schema"]
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        schema = _spec()["components"]["schemas"][ref]
    assert "discriminator" in schema
    assert schema["discriminator"]["propertyName"] == "action_type"
    refs = [item["$ref"].split("/")[-1] for item in schema["oneOf"]]
    assert len(refs) == 9


def test_openapi_badcase_summary_and_data_quality_contract() -> None:
    schemas = _spec()["components"]["schemas"]
    summary = schemas["BadcaseSummary"]
    assert set(summary["required"]) == REQUIRED_SUMMARY
    assert "P0" in summary["properties"]["severity"]["enum"]
    page = schemas["BadcasePage"]
    assert "data_quality" in page["required"]
    dq = schemas["DataQuality"]
    assert dq["properties"]["seed_or_mock_count"]["const"] == 0


def test_openapi_close_command_requires_closure_evidence() -> None:
    close = _spec()["components"]["schemas"]["BadcaseCloseCommand"]
    # allOf[1] holds the close-specific required fields
    required = set(close["allOf"][1]["required"])
    for field in (
        "closure_reason",
        "fix_or_policy_version",
        "regression_case_ref",
        "passing_evaluation_ref",
        "point_treatment_ref",
        "user_notification_ref",
    ):
        assert field in required


def test_openapi_conflict_response_for_version_and_terminal() -> None:
    post = _spec()["paths"]["/badcases/{badcaseId}/actions"]["post"]
    assert "409" in post["responses"]
    assert "403" in post["responses"]


def test_typed_action_constants_match_openapi() -> None:
    from app.modules.badcases.service import TYPED_ACTION_TYPES

    assert ACTION_TYPES == set(TYPED_ACTION_TYPES)


def test_operational_router_mounted_paths_exist() -> None:
    from app.modules.admin_console.incidents.operational_badcases import (
        operational_badcases_router,
    )

    paths = {getattr(r, "path", None) for r in operational_badcases_router.routes}
    assert "/badcases" in paths
    assert "/badcases/{badcase_id}" in paths
    assert "/badcases/{badcase_id}/timeline" in paths
    assert "/badcases/{badcase_id}/impacts" in paths
    assert "/badcases/{badcase_id}/actions" in paths
    assert "/badcases/compatibility" in paths


@pytest.mark.asyncio
async def test_facade_list_shape_includes_data_quality(monkeypatch) -> None:
    """Contract-level shape check against service helpers (no live DB)."""
    from app.modules.badcases.service import data_quality_block

    dq = data_quality_block(unknown_count=2)
    assert dq["seed_or_mock_count"] == 0
    assert dq["unknown_count"] == 2
    assert "fresh_at" in dq
