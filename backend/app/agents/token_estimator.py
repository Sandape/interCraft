"""TokenEstimator — per-node token consumption estimates (T011).

Uses fixed estimates per contracts/llm-client.md §Token 估算表.
Interview model policy: planner (plan gen) = deepseek-v4-pro;
all other LLM nodes = deepseek-v4-flash.
"""
from __future__ import annotations

import os

from app.core.config import get_settings

# Per-node token estimates (input + output combined)
NODE_TOKEN_ESTIMATES: dict[str, int] = {
    "intake": 700,
    "question_gen": 2500,
    "score": 1800,
    "score_llm": 1800,
    "report": 5500,
    "planner": 4000,
    "planner_generate": 4000,
    "compress_history": 1500,
    "variant_generator": 1200,
}

# Alias node_name → settings / fallback key (score_llm → score, etc.)
_NODE_ALIASES: dict[str, str] = {
    "score_llm": "score",
    "planner_generate": "planner",
}

# Fallback models when Settings is not available (tests)
_DEFAULT_MODEL_FALLBACK: dict[str, str] = {
    "planner": "deepseek-v4-pro",
    "planner_generate": "deepseek-v4-pro",
    "intake": "deepseek-v4-flash",
    "question_gen": "deepseek-v4-flash",
    "score": "deepseek-v4-flash",
    "score_llm": "deepseek-v4-flash",
    "report": "deepseek-v4-flash",
    "compress_history": "deepseek-v4-flash",
    "variant_generator": "deepseek-v4-flash",
}

_PRO_MODEL = "deepseek-v4-pro"
_FLASH_MODEL = "deepseek-v4-flash"


def _canonical_node(node_name: str) -> str:
    return _NODE_ALIASES.get(node_name, node_name)


def _get_per_node_model(node_name: str) -> str:
    """Resolve the model for a node. Priority:
    1. AGENT_MODEL_{NODE} env var (highest; tries exact then canonical)
    2. Settings deepseek_model_{node} (exact then canonical)
    3. Settings deepseek_model (global fallback)
    4. Hardcoded default (lowest)
    """
    exact = node_name
    canonical = _canonical_node(node_name)

    for key in (exact, canonical):
        env_override = os.environ.get(f"AGENT_MODEL_{key.upper()}")
        if env_override:
            return env_override

    try:
        settings = get_settings()
        for key in (exact, canonical):
            node_model = getattr(settings, f"deepseek_model_{key}", None)
            if node_model:
                return node_model
        return settings.deepseek_model
    except Exception:
        return _DEFAULT_MODEL_FALLBACK.get(exact) or _DEFAULT_MODEL_FALLBACK.get(
            canonical, _FLASH_MODEL
        )


def thinking_enabled_for_model(model: str) -> bool:
    """Thinking/reasoning only for pro; flash stays non-thinking for latency."""
    return model == _PRO_MODEL or model.endswith("-pro")


class TokenEstimator:
    """Estimates token consumption per node type for quota pre-deduction."""

    def estimate(self, node_name: str, model: str | None = None) -> int:
        return NODE_TOKEN_ESTIMATES.get(node_name, 3000)

    def get_model(self, node_name: str) -> str:
        """Return the model name for this node type.

        Respects AGENT_MODEL_* env var overrides, then per-node Settings, then global fallback.
        """
        return _get_per_node_model(node_name)


__all__ = [
    "NODE_TOKEN_ESTIMATES",
    "TokenEstimator",
    "_get_per_node_model",
    "thinking_enabled_for_model",
]
