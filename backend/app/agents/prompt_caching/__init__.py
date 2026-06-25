"""Prompt Caching & Token Cost Engineering library (feature 027 US1).

Self-contained library (Constitution Principle I: Library-First). No DB /
FastAPI direct dependency — only `hashlib` + `json` (stdlib) +
`prometheus_client` + `structlog` (already project deps).

US1 scope:
- `PromptLayer.prepare()` assembles messages with stable prefix
  (system_prompt + tool_defs + snapshot + requirements) before dynamic tail
- `CachePrefix` / `CacheHitRecord` / `LayeredPrompt` dataclasses
- `serialize_tool_definitions()`: deterministic alphabetical serialization
- `record_cache_hit()`: prometheus counters + structlog log
- `build_cache_control_headers()` / `build_cache_control_segments()`:
  DeepSeek V4 context caching protocol abstraction (PLACEHOLDER for US1)
- PII isolation: caller responsibility (FR-005)
- Graceful fallback: `record_cache_hit()` never raises (FR-008)

⏳ Deferred to US2/US3/US4 + later:
- US2 quota model (cached/uncached rate pricing, FR-010/011/012/013)
- US3 frontend quota display (raw vs effective tokens, FR-013)
- US4 eval suite cache hit rate regression (FR-018) — depends on 026
- DeepSeek V4 context caching protocol full verification — placeholder emitted
- 5 graph full integration — interview graph integration point in working tree
- LLMClient integration point (`invoke` calls `PromptLayer.prepare()` +
  `record_cache_hit()`) — `llm_client.py` working tree M, follows 024 landing
- MockLLMClient `cache_mode` parameter (FR-017 production mock) —
  `llm_client_mock.py` working tree M; FR-017 satisfied by test stub
  `_CacheSimulatingClient` in `tests/unit/test_prompt_caching.py`
"""
from app.agents.prompt_caching.layer import (
    CacheHitRecord,
    CachePrefix,
    LayeredPrompt,
    LLM_CACHE_CACHED_TOKENS_TOTAL,
    LLM_CACHE_DISCOUNT_TOKENS_TOTAL,
    LLM_CACHE_HIT_TOTAL,
    LLM_CACHE_UNCACHED_TOKENS_TOTAL,
    PromptLayer,
    build_cache_control_headers,
    build_cache_control_segments,
    compute_prefix_hash,
    record_cache_hit,
    serialize_tool_definitions,
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
