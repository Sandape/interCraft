"""Regression contract for the tracked REQ-061 capability registry fixture."""

from __future__ import annotations

from app.modules.ai_runtime.adapters.registry import load_registry
from app.modules.ai_runtime.adapters.resume_derive import ResumeDeriveAdapter


def test_registry_fixture_loads_resume_derive_contract() -> None:
    """The clean checkout must be able to construct the derive adapter."""
    load_registry.cache_clear()

    registry = load_registry()
    spec = registry[("resume_derive", "derive")]
    adapter = ResumeDeriveAdapter()
    envelope = adapter.build_acceptance_envelope(
        service_tier="standard",
        input_snapshot_ref="fixture://req-095",
        allow_degrade=True,
    )

    assert spec.engine_kind == "background_pipeline"
    assert tuple(m.code for m in spec.milestones) == (
        "draft",
        "job_analysis",
        "suggestions",
    )
    assert envelope.capability_code == "resume_derive"
    assert envelope.action_code == "derive"
    assert envelope.max_points == 300
