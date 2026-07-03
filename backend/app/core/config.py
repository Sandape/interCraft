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
    max_active_sessions: int = 5

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

    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @field_validator("log_level")
    @classmethod
    def _norm_log_level(cls, v: str) -> str:
        u = v.upper()
        if u not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            return "INFO"
        return u


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide Settings singleton (cached)."""
    return Settings()
