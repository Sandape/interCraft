"""032 (spec 027-prompt-caching-cost) US1 — Prompt Caching library.

Self-contained library (Constitution Principle I: Library-First). No DB /
FastAPI direct dependency — only `hashlib` + `json` (stdlib) +
`prometheus_client` + `structlog` (already project deps).

US1 scope:
- `PromptLayer.prepare()` assembles messages with stable prefix
  (system_prompt + tool_defs + snapshot + requirements) before dynamic tail
  (user message + current question + scores) — FR-001/003/004
- `CachePrefix` dataclass: prefix hash + component hashes + node + version
  — FR-009
- `CacheHitRecord` dataclass: per-invocation cache outcome — FR-007
- `serialize_tool_definitions()`: deterministic (alphabetical) serialization
  — FR-002
- `record_cache_hit()`: prometheus counters + structlog log — FR-014/015/016
- `build_cache_control_headers()` + `build_cache_control_segments()`:
  DeepSeek V4 context caching protocol abstraction (PLACEHOLDER for US1 —
  real protocol validated in plan phase, FR-006)
- PII isolation: caller responsibility — user free-text goes in
  `dynamic_messages`, never in `snapshot` / `requirements` / `system_prompt`
  — FR-005
- Graceful fallback: `record_cache_hit()` never raises; cache unavailable
  → uncached invocation + structured warning — FR-008

⏳ Deferred to US2/US3/US4 + later:
- US2 quota model (cached/uncached rate pricing, FR-010/011/012/013) — needs
  LLMClient `_pre_deduct` / `_actual_adjust` changes + `PricingConfig` table
- US3 frontend quota display (raw vs effective tokens, FR-013) — needs
  frontend Settings page changes
- US4 eval suite cache hit rate regression (FR-018) — depends on 026 eval
  suite extension
- DeepSeek V4 context caching protocol full verification — placeholder
  emitted by `build_cache_control_headers()` / `build_cache_control_segments()`
- 5 graph full integration — US1 only does interview graph integration point
  (in working tree, not committed); resume_optimize / ability_diagnose /
  general_coach / error_coach ⏳
- LLMClient integration point (in `invoke` call `PromptLayer.prepare()` +
  `record_cache_hit()`) — `llm_client.py` is working tree M state (024
  leftover), follows 024 landing, not committed here
- MockLLMClient `cache_mode` parameter (FR-017 production mock) —
  `llm_client_mock.py` is working tree M state; FR-017 satisfied by test
  stub `_CacheSimulatingClient` in `tests/unit/test_prompt_caching.py`
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger("agents.prompt_caching")

# ---------------------------------------------------------------------------
# Prometheus metrics (FR-014, FR-016)
# ---------------------------------------------------------------------------
try:
    from prometheus_client import Counter

    LLM_CACHE_HIT_TOTAL = Counter(
        "llm_cache_hit_total",
        "LLM cache hit/miss by node, graph, result",
        ["node", "graph", "result"],  # result=hit|miss
    )
    LLM_CACHE_CACHED_TOKENS_TOTAL = Counter(
        "llm_cache_cached_tokens_total",
        "LLM cached input tokens by node, graph",
        ["node", "graph"],
    )
    LLM_CACHE_UNCACHED_TOKENS_TOTAL = Counter(
        "llm_cache_uncached_tokens_total",
        "LLM uncached input tokens by node, graph",
        ["node", "graph"],
    )
    LLM_CACHE_DISCOUNT_TOKENS_TOTAL = Counter(
        "llm_cache_discount_tokens_total",
        "LLM cache discount (tokens saved) by user, graph",
        ["user_id", "graph"],
    )
except ImportError:  # pragma: no cover
    LLM_CACHE_HIT_TOTAL = None  # type: ignore[assignment]
    LLM_CACHE_CACHED_TOKENS_TOTAL = None  # type: ignore[assignment]
    LLM_CACHE_UNCACHED_TOKENS_TOTAL = None  # type: ignore[assignment]
    LLM_CACHE_DISCOUNT_TOKENS_TOTAL = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CachePrefix:
    """Stable prefix assembly for one LLM call.

    Attributes
    ----------
    prefix_hash:
        Aggregate SHA256 of all stable component hashes (sorted by key,
        `|`-joined `k:hash` pairs, then SHA256). Used as the cache lookup key.
    component_hashes:
        Per-component SHA256 for each stable segment (system_prompt,
        tool_defs, snapshot, requirements). Used for cache miss diagnosis
        — which component changed.
    node:
        Node name (e.g. "intake", "score", "report"). Included for
        observability; NOT part of the hash (same prefix used by different
        nodes would share a cache entry).
    version:
        Schema version for cache invalidation. Bump when the prompt
        layering structure changes (e.g. new component type added) so all
        cached prefixes are invalidated.
    """

    prefix_hash: str
    component_hashes: dict[str, str]
    node: str
    version: str = "v1"


@dataclass(frozen=True)
class CacheHitRecord:
    """Per-invocation cache outcome.

    Attributes
    ----------
    trace_id:
        OTel trace id (correlates with `app.observability.tracing`). Empty
        string if no active trace.
    node:
        Node name (e.g. "intake").
    prefix_hash:
        Stable prefix hash (from `CachePrefix.prefix_hash`).
    hit:
        True if cache hit on the stable prefix.
    cached_tokens:
        Input tokens served from cache (charged at cached rate in US2).
    uncached_tokens:
        Input tokens NOT served from cache (charged at full rate in US2).
    miss_reason:
        None on hit; one of "first-call", "prefix-changed",
        "ttl-expired", "provider-cache-unavailable" on miss (FR-015).
    cost_saved:
        Tokens saved by caching (cached_tokens × discount_factor; in US1
        the discount factor is 1.0 for simplicity, US2 will use real
        pricing from `PricingConfig`).
    """

    trace_id: str
    node: str
    prefix_hash: str
    hit: bool
    cached_tokens: int
    uncached_tokens: int
    miss_reason: str | None
    cost_saved: int


@dataclass
class LayeredPrompt:
    """Result of `PromptLayer.prepare()`.

    Attributes
    ----------
    messages:
        OpenAI-format messages with stable prefix first, dynamic tail last.
        Ready to pass to `LLMClient.invoke(messages=...)`.
    prefix:
        `CachePrefix` with component hashes for diagnosis.
    stable_token_count:
        Estimated tokens in the stable prefix (system_prompt + tool_defs +
        snapshot + requirements). Used for cache hit/miss token accounting.
    dynamic_token_count:
        Estimated tokens in the dynamic tail (user message + current
        question + scores).
    """

    messages: list[dict[str, str]]
    prefix: CachePrefix
    stable_token_count: int
    dynamic_token_count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sha256(text: str) -> str:
    """SHA256 hex digest of UTF-8 encoded text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _estimate_tokens(text: str) -> int:
    """Rough CJK-friendly token estimate.

    1 CJK char ≈ 1.5 token; 1 ASCII char ≈ 0.25 token. Used only for
    `stable_token_count` / `dynamic_token_count` reporting — actual billing
    uses provider's `response.usage.prompt_tokens`.
    """
    if not text:
        return 0
    cjk = sum(1 for c in text if ord(c) > 0x2E80)
    ascii_ = len(text) - cjk
    return int(cjk * 1.5 + ascii_ * 0.25)


def compute_prefix_hash(component_hashes: dict[str, str]) -> str:
    """Aggregate prefix hash from component hashes.

    Components are sorted by key for deterministic aggregation — the order
    of keys in the input dict does not affect the output hash.
    """
    parts = [f"{k}:{component_hashes[k]}" for k in sorted(component_hashes)]
    return _sha256("|".join(parts))


def _tool_name(td: dict[str, Any]) -> str:
    """Extract tool name from OpenAI tool format or plain dict format."""
    fn = td.get("function")
    if isinstance(fn, dict):
        name: Any = fn.get("name", "")
    else:
        name = td.get("name", "")
    if isinstance(name, str):
        return name
    return ""


def serialize_tool_definitions(tool_defs: list[dict[str, Any]]) -> str:
    """Serialize tool definitions in deterministic (alphabetical) order.

    FR-002: Tool definitions MUST be serialized in a deterministic order
    (alphabetical by tool name) so adding a tool does not reorder existing
    entries and invalidate the cache.

    Two-stage sort:
    1. Outer list sorted by tool name (`function.name` for OpenAI format,
       `name` for plain dict format)
    2. Inner dict fields sorted by key via `json.dumps(sort_keys=True)`
    """
    if not tool_defs:
        return ""
    sorted_defs = sorted(tool_defs, key=_tool_name)
    return json.dumps(sorted_defs, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
# PromptLayer
# ---------------------------------------------------------------------------
class PromptLayer:
    """Assembles LLM messages with stable prefix + dynamic tail.

    Constitution Principle I (Library-First): self-contained, no DB / FastAPI
    dependency. The caller provides stable components (system prompt, tool
    defs, resume snapshot, requirements) and dynamic messages; PromptLayer
    assembles them in the cacheable order and computes prefix hashes.

    FR-001: cacheable prefix (system prompt, tool defs, snapshot, requirements)
            precedes dynamic tail (user message, current question, scores).
    FR-003: Resume snapshot in cacheable prefix when unchanged.
    FR-004: Per-call dynamic content in dynamic tail, never in prefix.
    FR-005: PII from user input MUST NOT appear in the cacheable prefix
            (caller responsibility — `prepare()` does not inspect content
            for PII; the caller MUST place user free-text in
            `dynamic_messages`, never in `snapshot` / `requirements` /
            `system_prompt`).
    FR-009: prefix hash computed for each stable segment (`component_hashes`).
    """

    VERSION = "v1"

    def prepare(
        self,
        *,
        system_prompt: str,
        tool_defs: list[dict[str, Any]] | None = None,
        snapshot: str | None = None,
        requirements: str | None = None,
        dynamic_messages: list[dict[str, str]] | None = None,
        node: str = "unknown",
    ) -> LayeredPrompt:
        """Assemble messages with stable prefix first, dynamic tail last.

        Order (FR-001):
        1. system_prompt (always, as system role)
        2. tool_defs serialized (as system role with [TOOLS] marker)
        3. snapshot (as system role with [SNAPSHOT] marker)
        4. requirements (as system role with [REQUIREMENTS] marker)
        5. dynamic_messages (as-is, FR-004)

        PII (FR-005): caller responsibility — do NOT pass user free-text
        in `snapshot` / `requirements` / `system_prompt`. Only structured,
        stable content goes in the prefix. `prepare()` does not inspect
        content for PII; it relies on the caller to honor this contract.
        """
        # --- Build stable prefix messages ---
        prefix_messages: list[dict[str, str]] = []

        # 1. System prompt — always first.
        prefix_messages.append({"role": "system", "content": system_prompt})

        # 2. Tool definitions — serialized deterministically (FR-002).
        tool_defs_str = ""
        if tool_defs:
            tool_defs_str = serialize_tool_definitions(tool_defs)
            prefix_messages.append(
                {
                    "role": "system",
                    "content": f"[TOOLS]\n{tool_defs_str}",
                }
            )

        # 3. Resume snapshot — stable within a session (FR-003).
        if snapshot:
            prefix_messages.append(
                {
                    "role": "system",
                    "content": f"[SNAPSHOT]\n{snapshot}",
                }
            )

        # 4. Requirements block — stable within a session (FR-003).
        if requirements:
            prefix_messages.append(
                {
                    "role": "system",
                    "content": f"[REQUIREMENTS]\n{requirements}",
                }
            )

        # 5. Dynamic tail — per-call content (FR-004).
        dynamic_messages_list: list[dict[str, str]] = list(dynamic_messages or [])
        all_messages = prefix_messages + dynamic_messages_list

        # --- Compute component hashes (FR-009) ---
        component_hashes: dict[str, str] = {
            "system_prompt": _sha256(system_prompt),
        }
        if tool_defs_str:
            component_hashes["tool_defs"] = _sha256(tool_defs_str)
        if snapshot:
            component_hashes["snapshot"] = _sha256(snapshot)
        if requirements:
            component_hashes["requirements"] = _sha256(requirements)

        prefix_hash = compute_prefix_hash(component_hashes)

        # --- Token estimates (rough — actual billing uses provider usage) ---
        stable_token_count = _estimate_tokens(
            system_prompt
            + tool_defs_str
            + (snapshot or "")
            + (requirements or "")
        )
        dynamic_token_count = sum(
            _estimate_tokens(m.get("content", "")) for m in dynamic_messages_list
        )

        return LayeredPrompt(
            messages=all_messages,
            prefix=CachePrefix(
                prefix_hash=prefix_hash,
                component_hashes=component_hashes,
                node=node,
                version=self.VERSION,
            ),
            stable_token_count=stable_token_count,
            dynamic_token_count=dynamic_token_count,
        )


# ---------------------------------------------------------------------------
# DeepSeek V4 context caching protocol (PLACEHOLDER for US1)
# ---------------------------------------------------------------------------
# DeepSeek V4 Pro supports context caching: stable prefixes are auto-cached
# server-side, and subsequent calls with the same prefix get a discount on
# input tokens. The specific protocol (cache_control header / segment marker
# / prefix hash) is validated in plan phase — this module provides an
# abstraction layer that the LLMClient integration point will use.
#
# US1 scope: emit prefix hash + structured log + prometheus metric.
# DeepSeek protocol adapter (cache_control header / segment marker) ⏳
# deferred to plan-phase verification.


def build_cache_control_headers(prefix: CachePrefix) -> dict[str, str]:
    """Build cache-control headers for the DeepSeek V4 API.

    PLACEHOLDER (US1): emits the prefix hash as a diagnostic header.
    DeepSeek V4's actual context caching protocol (cache_control segment
    marker / prefix hash header) is validated in plan phase. This function
    is the integration point — when the protocol is confirmed, this will
    emit the correct header / segment marker.

    FR-006: LLM client MUST emit cache-control signals per the provider's
    protocol for segments marked as stable.

    Returns
    -------
    dict[str, str]
        Headers to add to the DeepSeek API request. US1 emits:
        - `X-InterCraft-Prefix-Hash`: prefix hash for cache lookup
        - `X-InterCraft-Cache-Version`: schema version for invalidation
    """
    return {
        "X-InterCraft-Prefix-Hash": prefix.prefix_hash,
        "X-InterCraft-Cache-Version": prefix.version,
    }


def build_cache_control_segments(prefix: CachePrefix) -> list[dict[str, Any]]:
    """Build cache-control segment markers for OpenAI-format messages.

    PLACEHOLDER (US1): returns segment markers for each stable component.
    DeepSeek V4's actual segment marker format is validated in plan phase.

    FR-006: emit cache-control signals per the provider's protocol.

    Returns
    -------
    list[dict[str, Any]]
        One segment per stable component, in alphabetical order:
        `{"component": <name>, "hash": <sha256>, "cacheable": True}`
    """
    segments: list[dict[str, Any]] = []
    for component_name in sorted(prefix.component_hashes.keys()):
        segments.append(
            {
                "component": component_name,
                "hash": prefix.component_hashes[component_name],
                "cacheable": True,
            }
        )
    return segments


# ---------------------------------------------------------------------------
# Cache hit recording (FR-014, FR-015, FR-016, FR-008)
# ---------------------------------------------------------------------------
def record_cache_hit(
    record: CacheHitRecord,
    *,
    graph: str = "unknown",
    user_id: str | None = None,
) -> None:
    """Record cache hit/miss in prometheus + structured log.

    FR-014: cache hit rate metric per node + per graph.
    FR-015: cache miss log with prefix hash + miss reason.
    FR-016: cache discount applied counter per user + per graph.
    FR-008: graceful fallback — never raises; all metric/log failures
            are swallowed.

    Parameters
    ----------
    record:
        `CacheHitRecord` from the LLM invocation.
    graph:
        Graph name (e.g. "interview", "error_coach") for per-graph metrics.
    user_id:
        User id for per-user discount counter. None if unknown (e.g.
        system-level call).
    """
    result = "hit" if record.hit else "miss"

    # --- Prometheus counters (best-effort, FR-014/016) ---
    if LLM_CACHE_HIT_TOTAL is not None:
        try:
            LLM_CACHE_HIT_TOTAL.labels(
                node=record.node, graph=graph, result=result
            ).inc()
        except Exception:
            logger.warning(
                "llm.cache.metric_failed",
                counter="LLM_CACHE_HIT_TOTAL",
                exc_info=True,
            )

    if LLM_CACHE_CACHED_TOKENS_TOTAL is not None:
        try:
            LLM_CACHE_CACHED_TOKENS_TOTAL.labels(
                node=record.node, graph=graph
            ).inc(record.cached_tokens)
        except Exception:
            logger.warning(
                "llm.cache.metric_failed",
                counter="LLM_CACHE_CACHED_TOKENS_TOTAL",
                exc_info=True,
            )

    if LLM_CACHE_UNCACHED_TOKENS_TOTAL is not None:
        try:
            LLM_CACHE_UNCACHED_TOKENS_TOTAL.labels(
                node=record.node, graph=graph
            ).inc(record.uncached_tokens)
        except Exception:
            logger.warning(
                "llm.cache.metric_failed",
                counter="LLM_CACHE_UNCACHED_TOKENS_TOTAL",
                exc_info=True,
            )

    if record.cost_saved > 0 and LLM_CACHE_DISCOUNT_TOKENS_TOTAL is not None:
        try:
            LLM_CACHE_DISCOUNT_TOKENS_TOTAL.labels(
                user_id=user_id or "unknown",
                graph=graph,
            ).inc(record.cost_saved)
        except Exception:
            logger.warning(
                "llm.cache.metric_failed",
                counter="LLM_CACHE_DISCOUNT_TOKENS_TOTAL",
                exc_info=True,
            )

    # --- Structured log (FR-015) ---
    if record.hit:
        logger.info(
            "llm.cache.hit",
            trace_id=record.trace_id,
            node=record.node,
            graph=graph,
            prefix_hash=record.prefix_hash,
            cached_tokens=record.cached_tokens,
            uncached_tokens=record.uncached_tokens,
            cost_saved=record.cost_saved,
            user_id=user_id,
        )
    else:
        # FR-008: cache miss with structured warning (graceful fallback —
        # no user-facing error, but diagnostic log emitted).
        logger.info(
            "llm.cache.miss",
            trace_id=record.trace_id,
            node=record.node,
            graph=graph,
            prefix_hash=record.prefix_hash,
            cached_tokens=record.cached_tokens,
            uncached_tokens=record.uncached_tokens,
            miss_reason=record.miss_reason or "unknown",
            user_id=user_id,
        )


__all__ = [
    "CacheHitRecord",
    "CachePrefix",
    "LayeredPrompt",
    "LLM_CACHE_CACHED_TOKENS_TOTAL",
    "LLM_CACHE_DISCOUNT_TOKENS_TOTAL",
    "LLM_CACHE_HIT_TOTAL",
    "LLM_CACHE_UNCACHED_TOKENS_TOTAL",
    "PromptLayer",
    "build_cache_control_headers",
    "build_cache_control_segments",
    "compute_prefix_hash",
    "record_cache_hit",
    "serialize_tool_definitions",
]
