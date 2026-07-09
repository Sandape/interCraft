"""Application settings loaded from env vars.

Uses pydantic-settings BaseSettings. Values map directly to environment
variables (case-insensitive). See `.env.example` for the full list.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Phase 1 application settings.

    All fields are populated from environment variables (or `.env` file
    in the backend/ directory during local dev). Production values come
    from the environment only.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    app_env: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    # Stored as raw string from env; transformed via validator below.
    cors_allowed_origins: str = "http://localhost:5173"

    # ---- Database ----
    database_url: str = Field(
        default="postgresql+asyncpg://PLACEHOLDER:PLACEHOLDER@localhost:5432/intercraft"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_echo: bool = False
    # asyncpg uses `ssl` (not libpq's `sslmode`); values: "disable" | "prefer" | "require" | "verify-ca" | "verify-full", or None.
    db_ssl: str | None = None
    # When true, the engine uses NullPool so every checkout opens a fresh
    # connection. Critical for tests where RLS `app.user_id` must not leak
    # across requests via connection reuse.
    db_use_null_pool: bool = False

    # ---- Redis ----
    redis_url: str = "redis://localhost:6379/0"

    # ---- Security ----
    jwt_secret: str = "dev-only-dummy-32bytes-xxxxxxxxxxxxxxxxxxxxxx"
    jwt_algorithm: str = "HS256"
    access_ttl: int = 900  # 15 min
    # Account lifecycle
    account_deletion_grace_days: int = 7
    account_purge_days: int = 90
    export_expiry_hours: int = 72
    refresh_ttl: int = 604800  # 7 days
    bcrypt_cost_rounds: int = 12
    master_key: str = "ZGV2LW9ubHktZHVtbXktMzJiLWJhc2U2NC0xMjM0NTY3ODkwYWI="

    # ---- Sessions ----
    max_active_sessions: int = 10

    # ---- Export ----
    export_storage_path: str = "/tmp/exports/"

    # ---- Rate limit ----
    rate_limit_auth_per_min: int = 10
    rate_limit_business_per_min: int = 600

    # ---- AI / LLM (Phase 4) — DeepSeek V4 Pro via OpenAI-compatible API ----
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-pro"
    monthly_token_quota: int = 500_000
    deepseek_thinking_enabled: bool = True
    deepseek_reasoning_effort: str = "high"
    # Per-node model overrides (empty = use deepseek_model)
    deepseek_model_intake: str = "deepseek-v4-flash"
    deepseek_model_question_gen: str = "deepseek-v4-flash"
    deepseek_model_score: str = "deepseek-v4-pro"
    deepseek_model_report: str = "deepseek-v4-pro"

    # ---- Web search (Phase 5) — Tavily for ``tavily_search`` @tool (FR-004) ----
    # Empty default by design: ``tavily_search.ainvoke`` raises
    # ``TavilyAPIKeyMissingError`` (per AC-4.1a) when this is empty.
    tavily_api_key: str = ""
    tavily_mock_mode: bool = False

    # ---- Crypto versioning ----
    crypto_key_version: int = 1

    # ---- Avatar (Feature 013) ----
    avatar_storage_dir: str = "backend/.data/avatars"
    avatar_max_bytes: int = 2_097_152  # 2 MB
    avatar_max_dimension: int = 2048

    # ---- REQ-041 US1 FR-007 — ``@node_error_handler`` + ``state.error`` dual-track flag ----
    # Independently toggles the 041 US1 error-handling refactor (FR-002 + FR-003).
    # Independent of (and intentionally NAMESpaced away from):
    #   * 040 US1 ``INTERVIEW_USE_V2_STATE_SCHEMA`` in app.agents.interview.config
    #   * 040 US2 ``INTERVIEW_USE_V2_NODE_SPLIT``  in app.agents.interview.config
    #   * 041 US2 ``AGENT_USE_V2_TOOL_BINDING``    (deferred to US-2 MB4)
    # Default ``false`` ⇒ legacy behaviour (no decorator, no state.error);
    # flip to ``true`` to opt every LLM node into the new contract.
    # TODO(release-manager): drop this flag after the 1-week dual-track window.
    agent_use_v2_error_handler: bool = False

    # ---- REQ-041 US2 FR-007 — ``bind_tools`` + control-flow tools dual-track flag ----
    # Independently toggles the 041 US2 @tool / bind_tools roll-out (FR-004 +
    # FR-005). Each flag is intentionally a separate boolean so call sites can
    # adopt tool-binding + control-flow tools independently during the 1-week
    # observation window.
    #
    # AGENT_USE_V2_TOOL_BINDING
    #   when False (default): nodes call the query_* tools / tavily_search
    #       via direct function calls (legacy behaviour).
    #   when True: nodes opt in to ``llm.bind_tools([tavily_search, ...])``
    #       and the LLM owns tool-selection at the node level (per spec US-2 AS1).
    #
    # AGENT_USE_V2_CONTROL_TOOLS
    #   when False (default): agents have no access to ``think_tool`` /
    #       ``MarkComplete``; the legacy loop guards (correct_count >= 3)
    #       continue to drive completion.
    #   when True: ``think_tool`` + ``MarkComplete`` are bound alongside the
    #       query tools so the LLM can reflect (spec US-2 AS2) and self-terminate
    #       (spec US-2 AS3) — ``MarkComplete`` priority over ``correct_count``
    #       is enforced via the ``_mark_complete`` front-branch in
    #       ``loop_or_finish_node`` (AC-5.5a).
    #
    # Independent of:
    #   * 040 US1 ``INTERVIEW_USE_V2_STATE_SCHEMA`` in app.agents.interview.config
    #   * 040 US2 ``INTERVIEW_USE_V2_NODE_SPLIT``  in app.agents.interview.config
    #   * 041 US1 ``AGENT_USE_V2_ERROR_HANDLER`` above
    #
    # Default ``false`` ⇒ legacy behaviour preserved; flip to ``true`` to opt
    # individual agent nodes into the new contract.
    # TODO(release-manager): drop these flags after the 1-week observation window.
    agent_use_v2_tool_binding: bool = False
    agent_use_v2_control_tools: bool = False

    # ---- REQ-042 US-1 FR-009 / US-2 FR-009 — 3 dual-track flags ----
    # Each flag is intentionally a separate boolean (per L041-001 mini-batch
    # + FR-009 dual-track requirement) so call sites can adopt loop
    # termination, memory compression, and cross-session store independently
    # during the 1-week observation window.
    # TODO(release-manager): drop these flags after the 1-week observation window.
    us1_use_v2_loop_termination: bool = False
    us2_use_v2_compress_history: bool = False
    us2_use_v2_langgraph_store: bool = False

    # ---- REQ-043 US-1 FR-002 — LangSmith trace exporter ----
    # LangSmith runs in parallel with OTel (per FR-002 + openDeepResearch
    # deep_researcher.py:85 reference). When ``langsmith_api_key`` is empty
    # the exporter is a no-op (no network calls). Independent of (and
    # intentionally NAMESpaced away from) the REQ-040/041/042 env vars —
    # we use the ``langsmith_*`` prefix (per L041-004 namespace isolation)
    # rather than ``us1_use_v2_langsmith`` because LangSmith is an
    # external integration, not a dual-track switch.
    langsmith_api_key: str = ""
    langsmith_project: str = "intercraft-prod"

    # ---- REQ-045 LLM Ops / OTel-first eval workflow ----
    otel_enabled: bool = False
    otel_service_name: str = "intercraft-backend"
    otel_exporter_otlp_endpoint: str = ""
    otel_trace_sample_ratio: float = 1.0
    otel_propagators: str = "tracecontext,baggage"
    llm_ops_langsmith_sync_mode: str = "disabled"
    llm_ops_default_export_policy_version: str = "req045.v1"
    llm_ops_allow_prod_langsmith_full_content: bool = False
    llm_ops_langsmith_full_content_owner: str = ""
    llm_ops_langsmith_full_content_access_scope: str = ""
    llm_ops_langsmith_full_content_retention_days: int = 30

    # ---- REQ-043 US-2 FR-005 + FR-006 — Checkpointer 8-pool + 3-tier reconnect ----
    # ``us3_use_v2_checkpoint_pool`` toggles the new 8-pool sharding path
    # on/off (per FR-005 + FR-007 dual-track). Default ``false`` ⇒ use the
    # existing 023 single-pool ``get_checkpointer()`` path; flip to
    # ``true`` to opt into ``get_checkpointer_pool(user_id)`` routing.
    # ``checkpoint_pool_count`` defaults to 8 per Clarifications
    # 2026-07-03 (ship with 8 pools to avoid a future 4→8 migration).
    # Independent of (and intentionally NAMESpaced away from) the
    # 040/041/042 dual-track flags — per L041-004 cross-US namespace
    # isolation, US-2 uses ``us3_*`` prefix.
    # TODO(release-manager): drop this flag after the 1-week observation window.
    us3_use_v2_checkpoint_pool: bool = False
    checkpoint_pool_count: int = 8

    # ---- REQ-048 — Interview Mode Split + Doubao Card ----
    # Embedding + reranker service (single-process, both /embed + /rerank).
    embedding_service_url: str = "http://127.0.0.1:8765"
    embedding_model_name: str = "bge-small-zh-v1.5"
    embedding_timeout_seconds: int = 10
    reranker_service_url: str = "http://127.0.0.1:8765"
    reranker_model_name: str = "bge-reranker-v2-m3"
    reranker_timeout_seconds: int = 30
    # Card renderer (satori + resvg + sharp).
    card_renderer_url: str = "http://127.0.0.1:8766"
    card_render_timeout_seconds: int = 10
    # Cache TTLs.
    drill_cache_ttl_seconds: int = 300
    card_cache_ttl_days: int = 7
    # Full interview question-count envelope (FR-023).
    hard_min_questions_full: int = 7
    hard_max_questions_full: int = 15
    min_questions_full: int = 7
    max_questions_full: int = 15
    adaptive_termination_threshold: float = 8.0
    adaptive_termination_window: int = 3

    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @field_validator("log_level")
    @classmethod
    def _norm_log_level(cls, v: str) -> str:
        u = v.upper()
        if u not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            return "INFO"
        return u

    @field_validator("otel_trace_sample_ratio")
    @classmethod
    def _norm_otel_sample_ratio(cls, v: float) -> float:
        if v < 0:
            return 0.0
        if v > 1:
            return 1.0
        return v

    @field_validator("llm_ops_langsmith_sync_mode")
    @classmethod
    def _norm_langsmith_sync_mode(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in {"disabled", "optional", "required", "mock"}:
            return "disabled"
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide Settings singleton (cached)."""
    return Settings()
