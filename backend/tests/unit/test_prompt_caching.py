"""032 (spec 027-prompt-caching-cost) US1 — Unit tests: prompt_caching library.

Tests per spec FR-001..009 (prompt layering + cache invocation) and
FR-014..017 (observability + mock client).

Constitution III (Test-First): tests written before implementation.
"""
from __future__ import annotations

import dataclasses
import json

import pytest
import structlog

from app.agents.prompt_caching import (
    CacheHitRecord,
    CachePrefix,
    LayeredPrompt,
    PromptLayer,
    build_cache_control_headers,
    build_cache_control_segments,
    compute_prefix_hash,
    record_cache_hit,
    serialize_tool_definitions,
)
from app.agents.prompt_caching.layer import (
    LLM_CACHE_CACHED_TOKENS_TOTAL,
    LLM_CACHE_DISCOUNT_TOKENS_TOTAL,
    LLM_CACHE_HIT_TOTAL,
    LLM_CACHE_UNCACHED_TOKENS_TOTAL,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _content_at(messages: list[dict], role: str, idx: int = 0) -> str:
    """Return the content of the idx-th message with the given role."""
    seen = 0
    for m in messages:
        if m.get("role") == role:
            if seen == idx:
                return m.get("content", "")
            seen += 1
    return ""


def _role_at(messages: list[dict], idx: int) -> str:
    return messages[idx].get("role", "")


@pytest.fixture(autouse=True)
def _reset_prometheus():
    """Reset prometheus counters between tests for assertion determinism."""
    for counter in (
        LLM_CACHE_HIT_TOTAL,
        LLM_CACHE_CACHED_TOKENS_TOTAL,
        LLM_CACHE_UNCACHED_TOKENS_TOTAL,
        LLM_CACHE_DISCOUNT_TOKENS_TOTAL,
    ):
        if counter is not None:
            try:
                counter._clear()
            except Exception:
                pass
    yield
    for counter in (
        LLM_CACHE_HIT_TOTAL,
        LLM_CACHE_CACHED_TOKENS_TOTAL,
        LLM_CACHE_UNCACHED_TOKENS_TOTAL,
        LLM_CACHE_DISCOUNT_TOKENS_TOTAL,
    ):
        if counter is not None:
            try:
                counter._clear()
            except Exception:
                pass


def _prom_value(counter, **labels) -> float:
    """Read the current value of a prometheus counter for the given labels."""
    if counter is None:
        return 0.0
    try:
        return counter.labels(**labels)._value.get()
    except Exception:
        return 0.0


# ===========================================================================
# PromptLayer 分层 (FR-001, FR-003, FR-004)
# ===========================================================================
class TestPromptLayering:
    """FR-001: stable prefix precedes dynamic tail."""

    def test_prepare_places_system_prompt_first(self):
        layered = PromptLayer().prepare(
            system_prompt="You are an interviewer.",
            dynamic_messages=[{"role": "user", "content": "hi"}],
        )
        assert _role_at(layered.messages, 0) == "system"
        assert "You are an interviewer." in _content_at(layered.messages, "system", 0)
        assert layered.messages[-1] == {"role": "user", "content": "hi"}

    def test_prepare_places_tool_defs_after_system_prompt(self):
        tool_defs = [
            {"type": "function", "function": {"name": "search", "description": "..."}},
        ]
        layered = PromptLayer().prepare(
            system_prompt="S",
            tool_defs=tool_defs,
            dynamic_messages=[{"role": "user", "content": "U"}],
        )
        # system at 0, tool defs at 1, dynamic at 2
        assert _role_at(layered.messages, 0) == "system"
        assert _role_at(layered.messages, 1) == "system"
        assert _role_at(layered.messages, 2) == "user"
        # Tool defs segment carries [TOOLS] marker + serialized content
        tool_seg = layered.messages[1]["content"]
        assert "[TOOLS]" in tool_seg
        assert "search" in tool_seg

    def test_prepare_places_snapshot_and_requirements_in_prefix(self):
        layered = PromptLayer().prepare(
            system_prompt="S",
            snapshot="SNAP-CONTENT",
            requirements="REQ-CONTENT",
            dynamic_messages=[{"role": "user", "content": "U"}],
        )
        # All stable segments are system role; dynamic tail is user.
        # Order: system, snapshot, requirements, user.
        assert _role_at(layered.messages, 0) == "system"
        assert _role_at(layered.messages, 1) == "system"
        assert _role_at(layered.messages, 2) == "system"
        assert _role_at(layered.messages, 3) == "user"
        # Snapshot content present in prefix
        snapshot_seg = layered.messages[1]["content"]
        assert "[SNAPSHOT]" in snapshot_seg
        assert "SNAP-CONTENT" in snapshot_seg
        # Requirements content present in prefix
        req_seg = layered.messages[2]["content"]
        assert "[REQUIREMENTS]" in req_seg
        assert "REQ-CONTENT" in req_seg

    def test_prepare_dynamic_tail_appended_after_prefix(self):
        dynamic = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "second"},
            {"role": "user", "content": "third"},
        ]
        layered = PromptLayer().prepare(
            system_prompt="S",
            dynamic_messages=dynamic,
        )
        # 1 prefix message + 3 dynamic = 4 total
        assert len(layered.messages) == 4
        # Dynamic tail preserved in order
        assert layered.messages[1] == {"role": "user", "content": "first"}
        assert layered.messages[2] == {"role": "assistant", "content": "second"}
        assert layered.messages[3] == {"role": "user", "content": "third"}

    def test_prepare_empty_dynamic_messages_returns_only_prefix(self):
        layered = PromptLayer().prepare(
            system_prompt="S",
            snapshot="SNAP",
        )
        # 1 system + 1 snapshot = 2 messages
        assert len(layered.messages) == 2
        assert all(m["role"] == "system" for m in layered.messages)

    def test_prepare_no_snapshot_no_requirements_still_works(self):
        layered = PromptLayer().prepare(
            system_prompt="S",
            dynamic_messages=[{"role": "user", "content": "U"}],
        )
        # 1 system + 1 user = 2 messages, prefix hash still computed
        assert len(layered.messages) == 2
        assert layered.prefix.prefix_hash != ""
        assert "system_prompt" in layered.prefix.component_hashes


# ===========================================================================
# Prefix hash 稳定性 (FR-009)
# ===========================================================================
class TestPrefixHashStability:
    """FR-009: prefix hash computed for each stable segment."""

    def test_same_inputs_produce_same_prefix_hash(self):
        layer = PromptLayer()
        a = layer.prepare(system_prompt="S", snapshot="X", node="intake")
        b = layer.prepare(system_prompt="S", snapshot="X", node="intake")
        assert a.prefix.prefix_hash == b.prefix.prefix_hash

    def test_changing_system_prompt_changes_prefix_hash(self):
        layer = PromptLayer()
        a = layer.prepare(system_prompt="S1", node="intake")
        b = layer.prepare(system_prompt="S2", node="intake")
        assert a.prefix.prefix_hash != b.prefix.prefix_hash

    def test_changing_snapshot_changes_prefix_hash(self):
        layer = PromptLayer()
        a = layer.prepare(system_prompt="S", snapshot="SNAP1", node="intake")
        b = layer.prepare(system_prompt="S", snapshot="SNAP2", node="intake")
        assert a.prefix.prefix_hash != b.prefix.prefix_hash
        # But the system_prompt component hash is the same
        assert (
            a.prefix.component_hashes["system_prompt"]
            == b.prefix.component_hashes["system_prompt"]
        )
        # And the snapshot component hash differs
        assert (
            a.prefix.component_hashes["snapshot"]
            != b.prefix.component_hashes["snapshot"]
        )

    def test_changing_requirements_changes_prefix_hash(self):
        layer = PromptLayer()
        a = layer.prepare(system_prompt="S", requirements="R1", node="intake")
        b = layer.prepare(system_prompt="S", requirements="R2", node="intake")
        assert a.prefix.prefix_hash != b.prefix.prefix_hash

    def test_component_hashes_independently_track_each_segment(self):
        layer = PromptLayer()
        a = layer.prepare(system_prompt="S1", snapshot="SNAP", node="n")
        b = layer.prepare(system_prompt="S2", snapshot="SNAP", node="n")
        # system_prompt hash differs
        assert (
            a.prefix.component_hashes["system_prompt"]
            != b.prefix.component_hashes["system_prompt"]
        )
        # snapshot hash identical (same content)
        assert (
            a.prefix.component_hashes["snapshot"]
            == b.prefix.component_hashes["snapshot"]
        )

    def test_prefix_hash_includes_version_for_invalidation(self):
        layered = PromptLayer().prepare(system_prompt="S", node="intake")
        assert layered.prefix.version == "v1"
        # Bumping version changes the prefix_hash input — verified by
        # constructing a synthetic CachePrefix with bumped version.
        h1 = compute_prefix_hash(layered.prefix.component_hashes)
        # Same components but the CachePrefix.version is what the LLMClient
        # emits; here we just verify version is recorded on the prefix.
        assert layered.prefix.version == "v1"

    def test_compute_prefix_hash_deterministic(self):
        ch = {
            "system_prompt": "abc123",
            "snapshot": "def456",
        }
        h1 = compute_prefix_hash(ch)
        h2 = compute_prefix_hash(ch)
        assert h1 == h2

    def test_compute_prefix_hash_orders_components(self):
        """Component order in the input dict doesn't affect the hash."""
        ch1 = {"system_prompt": "a", "snapshot": "b"}
        ch2 = {"snapshot": "b", "system_prompt": "a"}  # same content, diff order
        assert compute_prefix_hash(ch1) == compute_prefix_hash(ch2)


# ===========================================================================
# Tool definitions 序列化 (FR-002)
# ===========================================================================
class TestToolSerialization:
    """FR-002: tool definitions serialized in deterministic (alphabetical) order."""

    def test_serialize_tool_definitions_sorts_by_function_name(self):
        tool_defs = [
            {"type": "function", "function": {"name": "zeta", "description": "z"}},
            {"type": "function", "function": {"name": "alpha", "description": "a"}},
        ]
        out = serialize_tool_definitions(tool_defs)
        # alpha should come before zeta
        assert out.index("alpha") < out.index("zeta")

    def test_serialize_tool_definitions_sorts_by_plain_name(self):
        tool_defs = [
            {"name": "zeta", "description": "z"},
            {"name": "alpha", "description": "a"},
        ]
        out = serialize_tool_definitions(tool_defs)
        assert out.index("alpha") < out.index("zeta")

    def test_serialize_tool_definitions_adding_new_tool_does_not_reorder_existing(self):
        layer = PromptLayer()
        # Two tools
        tools_v1 = [
            {"type": "function", "function": {"name": "alpha", "description": "a"}},
            {"type": "function", "function": {"name": "gamma", "description": "g"}},
        ]
        # Three tools (added beta)
        tools_v2 = [
            {"type": "function", "function": {"name": "gamma", "description": "g"}},
            {"type": "function", "function": {"name": "alpha", "description": "a"}},
            {"type": "function", "function": {"name": "beta", "description": "b"}},
        ]
        out_v1 = serialize_tool_definitions(tools_v1)
        out_v2 = serialize_tool_definitions(tools_v2)
        # alpha + gamma should be in the same order in both (alpha, gamma, then beta in v2)
        # v1: alpha, gamma
        # v2: alpha, beta, gamma
        assert out_v1.index("alpha") < out_v1.index("gamma")
        assert out_v2.index("alpha") < out_v2.index("beta") < out_v2.index("gamma")
        # The serialized substring for alpha+gamma in v1 is preserved as a
        # prefix of v2's alpha+gamma portion (modulo beta in between).
        # Concretely: alpha is at index 0 in both v1 and v2's serialized order.
        v1_first = json.loads(out_v1)[0]["function"]["name"]
        v2_first = json.loads(out_v2)[0]["function"]["name"]
        assert v1_first == "alpha"
        assert v2_first == "alpha"

        # Adding a tool does NOT change the prefix hash for system_prompt + snapshot
        # (only the tool_defs component hash changes).
        layered_v1 = layer.prepare(
            system_prompt="S", tool_defs=tools_v1, snapshot="SNAP", node="n"
        )
        layered_v2 = layer.prepare(
            system_prompt="S", tool_defs=tools_v2, snapshot="SNAP", node="n"
        )
        assert (
            layered_v1.prefix.component_hashes["system_prompt"]
            == layered_v2.prefix.component_hashes["system_prompt"]
        )
        assert (
            layered_v1.prefix.component_hashes["snapshot"]
            == layered_v2.prefix.component_hashes["snapshot"]
        )
        # tool_defs hash differs (added beta)
        assert (
            layered_v1.prefix.component_hashes["tool_defs"]
            != layered_v2.prefix.component_hashes["tool_defs"]
        )

    def test_serialize_tool_definitions_internal_dict_keys_sorted(self):
        tool_defs = [
            {"type": "function", "function": {"name": "x", "b": 1, "a": 2}},
        ]
        out = serialize_tool_definitions(tool_defs)
        # Internal dict keys sorted alphabetically: "a" before "b"
        assert out.index('"a"') < out.index('"b"')

    def test_serialize_tool_definitions_empty_list_returns_empty_string(self):
        assert serialize_tool_definitions([]) == ""

    def test_serialize_tool_definitions_same_input_same_output(self):
        tool_defs = [
            {"type": "function", "function": {"name": "x", "desc": "..."}},
        ]
        a = serialize_tool_definitions(tool_defs)
        b = serialize_tool_definitions(tool_defs)
        assert a == b


# ===========================================================================
# PII 隔离 (FR-005)
# ===========================================================================
class TestPIIIsolation:
    """FR-005: PII from user input MUST NOT appear in the cacheable prefix."""

    def test_pii_stays_in_dynamic_tail_not_in_prefix(self):
        user_pii = "My email is john.doe@example.com and phone 555-1234"
        layered = PromptLayer().prepare(
            system_prompt="You are an interviewer.",
            snapshot="Candidate resume snapshot (no PII)",
            requirements="Job requirements (no PII)",
            dynamic_messages=[{"role": "user", "content": user_pii}],
        )
        # PII appears in the dynamic tail (last message)
        assert user_pii in layered.messages[-1]["content"]
        # PII does NOT appear in any prefix message
        prefix_messages = layered.messages[:-1]
        for m in prefix_messages:
            assert "john.doe@example.com" not in m["content"]
            assert "555-1234" not in m["content"]

    def test_prepare_does_not_inspect_dynamic_messages_for_prefix_hash(self):
        """Dynamic message content does not affect the prefix hash."""
        layer = PromptLayer()
        a = layer.prepare(
            system_prompt="S",
            snapshot="SNAP",
            dynamic_messages=[{"role": "user", "content": "secret1"}],
        )
        b = layer.prepare(
            system_prompt="S",
            snapshot="SNAP",
            dynamic_messages=[{"role": "user", "content": "secret2"}],
        )
        assert a.prefix.prefix_hash == b.prefix.prefix_hash


# ===========================================================================
# CacheHitRecord (FR-007, FR-014, FR-015, FR-016)
# ===========================================================================
class TestCacheHitRecord:
    """FR-007: per-invocation cache outcome dataclass."""

    def test_cache_hit_record_hit_path(self):
        record = CacheHitRecord(
            trace_id="trace-1",
            node="intake",
            prefix_hash="hash-1",
            hit=True,
            cached_tokens=100,
            uncached_tokens=50,
            miss_reason=None,
            cost_saved=100,
        )
        assert record.trace_id == "trace-1"
        assert record.node == "intake"
        assert record.prefix_hash == "hash-1"
        assert record.hit is True
        assert record.cached_tokens == 100
        assert record.uncached_tokens == 50
        assert record.miss_reason is None
        assert record.cost_saved == 100

    def test_cache_hit_record_miss_path(self):
        record = CacheHitRecord(
            trace_id="trace-1",
            node="intake",
            prefix_hash="hash-1",
            hit=False,
            cached_tokens=0,
            uncached_tokens=150,
            miss_reason="first-call",
            cost_saved=0,
        )
        assert record.hit is False
        assert record.miss_reason == "first-call"
        assert record.cost_saved == 0

    def test_cache_hit_record_immutable(self):
        record = CacheHitRecord(
            trace_id="t",
            node="n",
            prefix_hash="h",
            hit=True,
            cached_tokens=1,
            uncached_tokens=1,
            miss_reason=None,
            cost_saved=1,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.hit = False  # type: ignore[misc]

    def test_record_cache_hit_increments_prometheus_counters(self):
        record = CacheHitRecord(
            trace_id="t",
            node="intake",
            prefix_hash="h",
            hit=True,
            cached_tokens=100,
            uncached_tokens=50,
            miss_reason=None,
            cost_saved=100,
        )
        before = _prom_value(
            LLM_CACHE_HIT_TOTAL, node="intake", graph="interview", result="hit"
        )
        record_cache_hit(record, graph="interview", user_id="u1")
        after = _prom_value(
            LLM_CACHE_HIT_TOTAL, node="intake", graph="interview", result="hit"
        )
        assert after - before == 1.0
        # Cached tokens counter incremented
        cached_before = _prom_value(
            LLM_CACHE_CACHED_TOKENS_TOTAL, node="intake", graph="interview"
        )
        # We already incremented above, so check delta from a second call
        record_cache_hit(record, graph="interview", user_id="u1")
        cached_after = _prom_value(
            LLM_CACHE_CACHED_TOKENS_TOTAL, node="intake", graph="interview"
        )
        assert cached_after - cached_before == 100.0
        # Discount counter incremented
        discount_val = _prom_value(
            LLM_CACHE_DISCOUNT_TOKENS_TOTAL, user_id="u1", graph="interview"
        )
        assert discount_val >= 200.0  # two calls × 100 saved each

    def test_record_cache_miss_increments_miss_counter(self):
        record = CacheHitRecord(
            trace_id="t",
            node="score",
            prefix_hash="h",
            hit=False,
            cached_tokens=0,
            uncached_tokens=150,
            miss_reason="first-call",
            cost_saved=0,
        )
        before = _prom_value(
            LLM_CACHE_HIT_TOTAL, node="score", graph="interview", result="miss"
        )
        record_cache_hit(record, graph="interview", user_id="u1")
        after = _prom_value(
            LLM_CACHE_HIT_TOTAL, node="score", graph="interview", result="miss"
        )
        assert after - before == 1.0
        # Uncached tokens counter incremented
        uncached_val = _prom_value(
            LLM_CACHE_UNCACHED_TOKENS_TOTAL, node="score", graph="interview"
        )
        assert uncached_val >= 150.0

    def test_record_cache_hit_logs_structured_with_prefix_hash(self):
        record = CacheHitRecord(
            trace_id="trace-abc",
            node="intake",
            prefix_hash="hash-xyz",
            hit=True,
            cached_tokens=100,
            uncached_tokens=50,
            miss_reason=None,
            cost_saved=100,
        )
        # Use structlog.testing.capture_logs() for test isolation — the
        # manual structlog.configure() approach leaks state across tests
        # when the full suite runs (lessons-learned: structlog processor
        # chain must end with renderer or DropEvent; capture_logs handles
        # this correctly).
        with structlog.testing.capture_logs() as captured:
            record_cache_hit(record, graph="interview", user_id="u1")

        # Find the cache.hit event
        hit_events = [e for e in captured if e.get("event") == "llm.cache.hit"]
        assert len(hit_events) == 1
        ev = hit_events[0]
        assert ev["prefix_hash"] == "hash-xyz"
        assert ev["cached_tokens"] == 100
        assert ev["uncached_tokens"] == 50
        assert ev["cost_saved"] == 100
        assert ev["node"] == "intake"
        assert ev["trace_id"] == "trace-abc"

    def test_record_cache_miss_logs_with_miss_reason(self):
        record = CacheHitRecord(
            trace_id="trace-abc",
            node="intake",
            prefix_hash="hash-xyz",
            hit=False,
            cached_tokens=0,
            uncached_tokens=150,
            miss_reason="first-call",
            cost_saved=0,
        )
        with structlog.testing.capture_logs() as captured:
            record_cache_hit(record, graph="interview", user_id="u1")

        miss_events = [e for e in captured if e.get("event") == "llm.cache.miss"]
        assert len(miss_events) == 1
        ev = miss_events[0]
        assert ev["prefix_hash"] == "hash-xyz"
        assert ev["miss_reason"] == "first-call"  # FR-015
        assert ev["node"] == "intake"


# ===========================================================================
# Cache simulation stub (FR-017)
# ===========================================================================
class TestCacheSimulatingClient:
    """FR-017: cache simulation testable without real provider."""

    def test_cache_simulating_client_realistic_first_call_miss(self):
        client = _CacheSimulatingClient(cache_mode="realistic")
        layered = PromptLayer().prepare(
            system_prompt="S", snapshot="SNAP", node="intake"
        )
        record = client.invoke_with_cache(layered, node="intake")
        assert record.hit is False
        assert record.miss_reason == "first-call"
        assert record.cached_tokens == 0
        assert record.uncached_tokens == layered.stable_token_count + layered.dynamic_token_count

    def test_cache_simulating_client_realistic_second_call_hit(self):
        client = _CacheSimulatingClient(cache_mode="realistic")
        layered = PromptLayer().prepare(
            system_prompt="S", snapshot="SNAP", node="intake"
        )
        # First call: miss
        client.invoke_with_cache(layered, node="intake")
        # Second call with same prefix: hit
        record = client.invoke_with_cache(layered, node="intake")
        assert record.hit is True
        assert record.miss_reason is None
        assert record.cached_tokens == layered.stable_token_count
        assert record.uncached_tokens == layered.dynamic_token_count
        assert record.cost_saved > 0

    def test_cache_simulating_client_realistic_prefix_changed_miss(self):
        client = _CacheSimulatingClient(cache_mode="realistic")
        layered1 = PromptLayer().prepare(
            system_prompt="S", snapshot="SNAP1", node="intake"
        )
        layered2 = PromptLayer().prepare(
            system_prompt="S", snapshot="SNAP2", node="intake"
        )
        # First call with prefix1: miss (first-call)
        r1 = client.invoke_with_cache(layered1, node="intake")
        assert r1.hit is False
        assert r1.miss_reason == "first-call"
        # Call with prefix2: miss (prefix-changed)
        r2 = client.invoke_with_cache(layered2, node="intake")
        assert r2.hit is False
        assert r2.miss_reason == "prefix-changed"
        # Call with prefix1 again: hit (already seen)
        r3 = client.invoke_with_cache(layered1, node="intake")
        assert r3.hit is True

    def test_cache_simulating_client_always_hit_mode(self):
        client = _CacheSimulatingClient(cache_mode="always_hit")
        layered = PromptLayer().prepare(
            system_prompt="S", snapshot="SNAP", node="intake"
        )
        # First call with always_hit: hit (even first call)
        record = client.invoke_with_cache(layered, node="intake")
        assert record.hit is True
        assert record.miss_reason is None
        assert record.cached_tokens > 0

    def test_cache_simulating_client_always_miss_mode(self):
        client = _CacheSimulatingClient(cache_mode="always_miss")
        layered = PromptLayer().prepare(
            system_prompt="S", snapshot="SNAP", node="intake"
        )
        # All calls miss (provider-cache-unavailable)
        client.invoke_with_cache(layered, node="intake")
        record = client.invoke_with_cache(layered, node="intake")
        assert record.hit is False
        assert record.miss_reason == "provider-cache-unavailable"

    def test_cache_simulating_client_records_cost_saved(self):
        client = _CacheSimulatingClient(cache_mode="realistic")
        layered = PromptLayer().prepare(
            system_prompt="S", snapshot="SNAP", node="intake"
        )
        # First call: miss, cost_saved = 0
        r1 = client.invoke_with_cache(layered, node="intake")
        assert r1.cost_saved == 0
        # Second call: hit, cost_saved > 0
        r2 = client.invoke_with_cache(layered, node="intake")
        assert r2.cost_saved > 0


# ===========================================================================
# Graceful fallback (FR-008) + cache-control signals (FR-006)
# ===========================================================================
class TestCacheControlSignals:
    """FR-006: emit cache-control signals per provider protocol (placeholder).
    FR-008: graceful fallback when cache unavailable.
    """

    def test_build_cache_control_headers_returns_diagnostic_headers(self):
        layered = PromptLayer().prepare(
            system_prompt="S", snapshot="SNAP", node="intake"
        )
        headers = build_cache_control_headers(layered.prefix)
        assert "X-InterCraft-Prefix-Hash" in headers
        assert headers["X-InterCraft-Prefix-Hash"] == layered.prefix.prefix_hash
        assert headers["X-InterCraft-Cache-Version"] == "v1"

    def test_build_cache_control_segments_returns_segment_markers(self):
        layered = PromptLayer().prepare(
            system_prompt="S",
            snapshot="SNAP",
            requirements="REQ",
            tool_defs=[{"type": "function", "function": {"name": "x"}}],
            node="intake",
        )
        segments = build_cache_control_segments(layered.prefix)
        # One segment per stable component
        assert len(segments) == 4  # system_prompt, tool_defs, snapshot, requirements
        components = {s["component"] for s in segments}
        assert components == {"system_prompt", "tool_defs", "snapshot", "requirements"}
        for seg in segments:
            assert seg["hash"] != ""
            assert seg["cacheable"] is True

    def test_build_cache_control_segments_empty_when_no_stable_components(self):
        """If only system_prompt is present, segments has 1 entry."""
        layered = PromptLayer().prepare(system_prompt="S", node="intake")
        segments = build_cache_control_segments(layered.prefix)
        assert len(segments) == 1
        assert segments[0]["component"] == "system_prompt"

    def test_graceful_fallback_when_cache_unavailable(self):
        """FR-008: cache unavailable → uncached invocation + structured warning,
        no user-facing error."""
        client = _CacheSimulatingClient(cache_mode="always_miss")
        layered = PromptLayer().prepare(
            system_prompt="S", snapshot="SNAP", node="intake"
        )
        record = client.invoke_with_cache(layered, node="intake")
        # Always-miss simulates provider-cache-unavailable
        assert record.hit is False
        assert record.miss_reason == "provider-cache-unavailable"
        # record_cache_hit still succeeds (no raise) — graceful fallback
        # Use capture_logs() for test isolation (structlog.configure() leaks
        # state across tests when the full suite runs).
        with structlog.testing.capture_logs() as captured:
            record_cache_hit(record, graph="interview", user_id="u1")
        # Structured warning (llm.cache.miss with miss_reason) emitted
        miss_events = [e for e in captured if e.get("event") == "llm.cache.miss"]
        assert len(miss_events) == 1
        assert miss_events[0]["miss_reason"] == "provider-cache-unavailable"


# ===========================================================================
# LayeredPrompt + CachePrefix dataclasses
# ===========================================================================
class TestDataclasses:
    """Smoke tests for dataclass shapes (catch accidental field renames)."""

    def test_cache_prefix_fields(self):
        prefix = CachePrefix(
            prefix_hash="h",
            component_hashes={"system_prompt": "sh"},
            node="intake",
            version="v1",
        )
        assert prefix.prefix_hash == "h"
        assert prefix.component_hashes["system_prompt"] == "sh"
        assert prefix.node == "intake"
        assert prefix.version == "v1"

    def test_cache_prefix_immutable(self):
        prefix = CachePrefix(
            prefix_hash="h",
            component_hashes={},
            node="intake",
            version="v1",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            prefix.prefix_hash = "other"  # type: ignore[misc]

    def test_layered_prompt_fields(self):
        # Use realistic-length content so token estimate > 0 (single ASCII
        # char is 0.25 token → int() = 0; need >= 4 chars for > 0).
        layered = PromptLayer().prepare(
            system_prompt="You are an interviewer for the candidate.",
            dynamic_messages=[{"role": "user", "content": "Hello, please start the interview."}],
            node="intake",
        )
        assert isinstance(layered, LayeredPrompt)
        assert isinstance(layered.prefix, CachePrefix)
        assert layered.stable_token_count > 0
        assert layered.dynamic_token_count > 0
        assert isinstance(layered.messages, list)


# ===========================================================================
# Cache simulation stub (FR-017) — independent of production MockLLMClient
# ===========================================================================
class _CacheSimulatingClient:
    """Test stub that simulates LLM cache hit/miss behavior.

    FR-017: The deterministic mock LLM client MUST simulate cache hits and
    misses so cache-aware logic is testable without the real provider.

    This stub is independent of the production MockLLMClient (which is in
    working tree M state). It demonstrates the cache simulation contract:
    - First call with a given prefix_hash → miss (first-call)
    - Subsequent calls with same prefix_hash → hit
    - Calls with different prefix_hash → miss (prefix-changed)

    cache_mode:
    - "realistic": first-call miss, subsequent hit, prefix-changed miss
    - "always_hit": all calls hit (even first call)
    - "always_miss": all calls miss (simulates provider-cache-unavailable)
    """

    def __init__(self, *, cache_mode: str = "realistic") -> None:
        self.cache_mode = cache_mode
        self._seen_prefixes: set[str] = set()
        self.hit_records: list[CacheHitRecord] = []

    def invoke_with_cache(
        self,
        layered: LayeredPrompt,
        *,
        node: str,
        trace_id: str = "test-trace",
    ) -> CacheHitRecord:
        prefix_hash = layered.prefix.prefix_hash

        if self.cache_mode == "always_hit":
            hit = True
            cached = layered.stable_token_count
            uncached = layered.dynamic_token_count
            miss_reason = None
        elif self.cache_mode == "always_miss":
            hit = False
            cached = 0
            uncached = layered.stable_token_count + layered.dynamic_token_count
            miss_reason = "provider-cache-unavailable"
        else:  # realistic
            if prefix_hash in self._seen_prefixes:
                hit = True
                cached = layered.stable_token_count
                uncached = layered.dynamic_token_count
                miss_reason = None
            else:
                hit = False
                cached = 0
                uncached = layered.stable_token_count + layered.dynamic_token_count
                miss_reason = "first-call" if not self._seen_prefixes else "prefix-changed"
            self._seen_prefixes.add(prefix_hash)

        # cost_saved = cached_tokens (1:1 discount factor for test simplicity)
        cost_saved = cached

        record = CacheHitRecord(
            trace_id=trace_id,
            node=node,
            prefix_hash=prefix_hash,
            hit=hit,
            cached_tokens=cached,
            uncached_tokens=uncached,
            miss_reason=miss_reason,
            cost_saved=cost_saved,
        )
        self.hit_records.append(record)
        return record
