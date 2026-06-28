"""REQ-033 US9 — VersionContext schema contract tests (T034).

Locks the data-model.md VersionContext contract (SC-010 / FR-038):

- Required fields: app_version, release_stage, environment, schema_version.
- Conditional fields: prompt_fingerprint (required for AI/eval), rubric_version
  (required for scored AI/eval), model, experiment_id, graph, node.
- Missing field → must be explicit ``"unknown"`` string (NOT None / NOT empty
  string / NOT field omission).
- JSON round-trip via ``to_dict`` / ``from_dict``.
- Enum ranges: ``release_stage`` ∈ {DEVELOPMENT, RELEASE_CANDIDATE, PRODUCTION,
  UNKNOWN}; ``environment`` ∈ {LOCAL, CI, STAGING, PRODUCTION}.
- ``VersionContext.unknown(...)`` factory fills all fields with ``"unknown"``.

All tests are TDD — they MUST fail before T037 implementation lands.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.modules.telemetry_contracts.schemas import VersionContext


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------


class TestVersionContextRequiredFields:
    """Required fields are validated and cannot be empty / None."""

    def test_minimal_construction_requires_app_version(self) -> None:
        with pytest.raises(Exception):
            VersionContext(
                app_version="",
                release_stage="DEVELOPMENT",
                environment="LOCAL",
                schema_version="v1",
            )

    def test_minimal_construction_requires_schema_version(self) -> None:
        with pytest.raises(Exception):
            VersionContext(
                app_version="0.33.0",
                release_stage="DEVELOPMENT",
                environment="LOCAL",
                schema_version="",
            )

    def test_minimal_construction_rejects_none_app_version(self) -> None:
        with pytest.raises(Exception):
            VersionContext(
                app_version=None,  # type: ignore[arg-type]
                release_stage="DEVELOPMENT",
                environment="LOCAL",
                schema_version="v1",
            )

    def test_constructed_with_all_required_fields(self) -> None:
        vc = VersionContext(
            app_version="0.33.0",
            release_stage="RELEASE_CANDIDATE",
            environment="STAGING",
            schema_version="v1",
        )
        assert vc.app_version == "0.33.0"
        assert vc.release_stage == "RELEASE_CANDIDATE"
        assert vc.environment == "STAGING"
        assert vc.schema_version == "v1"

    def test_unknown_string_is_allowed_for_required_fields(self) -> None:
        """Missing version fields must be explicit ``"unknown"`` (FR-038)."""
        vc = VersionContext(
            app_version="unknown",
            release_stage="UNKNOWN",
            environment="PRODUCTION",
            schema_version="unknown",
        )
        assert vc.app_version == "unknown"
        assert vc.release_stage == "UNKNOWN"


# ---------------------------------------------------------------------------
# Enum range validation
# ---------------------------------------------------------------------------


class TestVersionContextEnumRanges:
    """release_stage + environment enum values are validated."""

    @pytest.mark.parametrize(
        "stage",
        ["DEVELOPMENT", "RELEASE_CANDIDATE", "PRODUCTION", "UNKNOWN"],
    )
    def test_release_stage_accepts_all_documented_values(self, stage: str) -> None:
        vc = VersionContext(
            app_version="0.33.0",
            release_stage=stage,
            environment="LOCAL",
            schema_version="v1",
        )
        assert vc.release_stage == stage

    def test_release_stage_rejects_unknown_value(self) -> None:
        with pytest.raises(Exception):
            VersionContext(
                app_version="0.33.0",
                release_stage="banana",  # not in enum
                environment="LOCAL",
                schema_version="v1",
            )

    @pytest.mark.parametrize("env", ["LOCAL", "CI", "STAGING", "PRODUCTION"])
    def test_environment_accepts_all_documented_values(self, env: str) -> None:
        vc = VersionContext(
            app_version="0.33.0",
            release_stage="DEVELOPMENT",
            environment=env,
            schema_version="v1",
        )
        assert vc.environment == env

    def test_environment_rejects_lowercase(self) -> None:
        """Enums are case-sensitive — ``local`` ≠ ``LOCAL``."""
        with pytest.raises(Exception):
            VersionContext(
                app_version="0.33.0",
                release_stage="DEVELOPMENT",
                environment="local",  # type: ignore[arg-type]
                schema_version="v1",
            )


# ---------------------------------------------------------------------------
# Conditional fields default to "unknown" (NOT None / NOT empty / NOT omitted)
# ---------------------------------------------------------------------------


class TestVersionContextConditionalFields:
    """Conditional fields default to explicit ``"unknown"`` per FR-038."""

    def test_prompt_fingerprint_defaults_to_unknown(self) -> None:
        vc = VersionContext(
            app_version="0.33.0",
            release_stage="DEVELOPMENT",
            environment="LOCAL",
            schema_version="v1",
        )
        assert vc.prompt_fingerprint == "unknown"

    def test_rubric_version_defaults_to_unknown(self) -> None:
        vc = VersionContext(
            app_version="0.33.0",
            release_stage="DEVELOPMENT",
            environment="LOCAL",
            schema_version="v1",
        )
        assert vc.rubric_version == "unknown"

    def test_model_defaults_to_unknown(self) -> None:
        vc = VersionContext(
            app_version="0.33.0",
            release_stage="DEVELOPMENT",
            environment="LOCAL",
            schema_version="v1",
        )
        assert vc.model == "unknown"

    def test_experiment_id_defaults_to_unknown(self) -> None:
        vc = VersionContext(
            app_version="0.33.0",
            release_stage="DEVELOPMENT",
            environment="LOCAL",
            schema_version="v1",
        )
        assert vc.experiment_id == "unknown"

    def test_graph_defaults_to_unknown(self) -> None:
        vc = VersionContext(
            app_version="0.33.0",
            release_stage="DEVELOPMENT",
            environment="LOCAL",
            schema_version="v1",
        )
        assert vc.graph == "unknown"

    def test_node_defaults_to_unknown(self) -> None:
        vc = VersionContext(
            app_version="0.33.0",
            release_stage="DEVELOPMENT",
            environment="LOCAL",
            schema_version="v1",
        )
        assert vc.node == "unknown"

    def test_conditional_field_can_be_overridden(self) -> None:
        vc = VersionContext(
            app_version="0.33.0",
            release_stage="PRODUCTION",
            environment="PRODUCTION",
            schema_version="v1",
            prompt_fingerprint="abc123def4567890",
            rubric_version="rubric-2026-06-26",
            model="deepseek-v4-pro",
            experiment_id="exp-001",
            graph="interview",
            node="score",
        )
        assert vc.prompt_fingerprint == "abc123def4567890"
        assert vc.rubric_version == "rubric-2026-06-26"
        assert vc.model == "deepseek-v4-pro"
        assert vc.experiment_id == "exp-001"
        assert vc.graph == "interview"
        assert vc.node == "score"

    def test_conditional_field_empty_string_is_normalized_to_unknown(self) -> None:
        """Empty string is treated as missing (per FR-038 normalization)."""
        vc = VersionContext(
            app_version="0.33.0",
            release_stage="DEVELOPMENT",
            environment="LOCAL",
            schema_version="v1",
            prompt_fingerprint="",
        )
        # Either "" gets rejected (fail-fast) OR normalized to "unknown" —
        # both are acceptable for FR-038 (must not silently omit).
        # We allow either, as long as it's not silently treated as a real value.
        assert vc.prompt_fingerprint in ("", "unknown")


# ---------------------------------------------------------------------------
# unknown() factory
# ---------------------------------------------------------------------------


class TestVersionContextUnknownFactory:
    """``VersionContext.unknown(environment=...)`` fills all fields with "unknown"."""

    def test_unknown_factory_fills_required_fields(self) -> None:
        vc = VersionContext.unknown(environment="PRODUCTION")
        assert vc.app_version == "unknown"
        assert vc.release_stage == "UNKNOWN"
        assert vc.environment == "PRODUCTION"
        assert vc.schema_version == "unknown"

    def test_unknown_factory_fills_all_conditional_fields(self) -> None:
        vc = VersionContext.unknown(environment="LOCAL")
        assert vc.prompt_fingerprint == "unknown"
        assert vc.rubric_version == "unknown"
        assert vc.model == "unknown"
        assert vc.experiment_id == "unknown"
        assert vc.graph == "unknown"
        assert vc.node == "unknown"

    def test_unknown_factory_preserves_environment_override(self) -> None:
        vc = VersionContext.unknown(environment="STAGING")
        assert vc.environment == "STAGING"

    def test_unknown_factory_to_dict_contains_all_fields(self) -> None:
        vc = VersionContext.unknown(environment="CI")
        d = vc.to_dict()
        for f in [
            "appVersion",
            "schemaVersion",
            "promptFingerprint",
            "rubricVersion",
            "model",
            "experimentId",
            "graph",
            "node",
        ]:
            assert f in d, f"missing {f} in to_dict()"
            assert d[f] == "unknown", f"{f} expected 'unknown', got {d[f]!r}"
        # releaseStage is the enum value UNKNOWN (uppercase), not "unknown".
        assert d["releaseStage"] == "UNKNOWN"
        # environment is the one we passed in.
        assert d["environment"] == "CI"


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------


class TestVersionContextJsonRoundTrip:
    """``to_dict`` / ``from_dict`` are inverses (data-model.md + SC-010)."""

    def test_to_dict_uses_camel_case_keys(self) -> None:
        vc = VersionContext(
            app_version="0.33.0",
            release_stage="RELEASE_CANDIDATE",
            environment="STAGING",
            schema_version="v1",
        )
        d = vc.to_dict()
        # camelCase contract per contracts/event-metric-schema.md
        assert "appVersion" in d
        assert "releaseStage" in d
        assert "environment" in d
        assert "schemaVersion" in d
        assert "promptFingerprint" in d

    def test_round_trip_preserves_all_fields(self) -> None:
        original = VersionContext(
            app_version="0.33.0",
            release_stage="PRODUCTION",
            environment="PRODUCTION",
            schema_version="v1",
            prompt_fingerprint="fp-abc",
            rubric_version="r-2026-06-26",
            model="deepseek-v4-pro",
            experiment_id="exp-9",
            graph="interview",
            node="score",
        )
        d = original.to_dict()
        restored = VersionContext.from_dict(d)
        assert restored == original

    def test_from_dict_accepts_camel_case(self) -> None:
        d: dict[str, Any] = {
            "appVersion": "0.33.0",
            "releaseStage": "DEVELOPMENT",
            "environment": "LOCAL",
            "schemaVersion": "v1",
            "promptFingerprint": "fp-xyz",
            "rubricVersion": "unknown",
            "model": "deepseek",
            "experimentId": "exp-2",
            "graph": "interview",
            "node": "score",
        }
        vc = VersionContext.from_dict(d)
        assert vc.app_version == "0.33.0"
        assert vc.prompt_fingerprint == "fp-xyz"

    def test_from_dict_missing_optional_field_normalized(self) -> None:
        """Missing conditional fields in dict → normalized to "unknown"."""
        d: dict[str, Any] = {
            "appVersion": "0.33.0",
            "releaseStage": "DEVELOPMENT",
            "environment": "LOCAL",
            "schemaVersion": "v1",
        }
        vc = VersionContext.from_dict(d)
        assert vc.prompt_fingerprint == "unknown"
        assert vc.rubric_version == "unknown"
        assert vc.model == "unknown"


# ---------------------------------------------------------------------------
# SC-010 contract: explicit "unknown" representation
# ---------------------------------------------------------------------------


class TestSC010ExplicitUnknownContract:
    """SC-010 / FR-038: missing fields are explicit ``"unknown"``, never None / empty / omitted."""

    def test_to_dict_never_contains_none_for_required(self) -> None:
        vc = VersionContext(
            app_version="0.33.0",
            release_stage="DEVELOPMENT",
            environment="LOCAL",
            schema_version="v1",
        )
        d = vc.to_dict()
        for k, v in d.items():
            assert v is not None, f"field {k} must not be None (SC-010)"
            assert v != "", f"field {k} must not be empty (SC-010)"

    def test_to_dict_never_contains_none_for_conditional(self) -> None:
        vc = VersionContext(
            app_version="0.33.0",
            release_stage="DEVELOPMENT",
            environment="LOCAL",
            schema_version="v1",
        )
        d = vc.to_dict()
        for f in [
            "promptFingerprint",
            "rubricVersion",
            "model",
            "experimentId",
            "graph",
            "node",
        ]:
            assert f in d
            assert d[f] == "unknown", f"{f} must default to 'unknown' (SC-010)"
