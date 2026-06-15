"""TokenEstimator — per-node token consumption estimates (T011).

Uses fixed estimates per contracts/llm-client.md §Token 估算表.
Per-node model tiering: flash for live-interview nodes, pro for evaluation/report.
"""
from __future__ import annotations

import os

from app.core.config import get_settings

# Per-node token estimates (input + output combined)
NODE_TOKEN_ESTIMATES: dict[str, int] = {
    "intake": 700,
    "question_gen": 2500,
    "score": 1800,
    "report": 5500,
}

# Fallback models when Settings is not available (tests)
_DEFAULT_MODEL_FALLBACK: dict[str, str] = {
    "intake": "deepseek-v4-flash",
    "question_gen": "deepseek-v4-flash",
    "score": "deepseek-v4-pro",
    "report": "deepseek-v4-pro",
}


def _get_per_node_model(node_name: str) -> str:
    """Resolve the model for a node. Priority:
    1. AGENT_MODEL_{NODE} env var (highest)
    2. Settings deepseek_model_{node}
    3. Settings deepseek_model (global fallback)
    4. Hardcoded default (lowest)
    """
    env_key = f"AGENT_MODEL_{node_name.upper()}"
    env_override = os.environ.get(env_key)
    if env_override:
        return env_override

    try:
        settings = get_settings()
        node_model = getattr(settings, f"deepseek_model_{node_name}", None)
        if node_model:
            return node_model
        return settings.deepseek_model
    except Exception:
        return _DEFAULT_MODEL_FALLBACK.get(node_name, "deepseek-v4-pro")


class TokenEstimator:
    """Estimates token consumption per node type for quota pre-deduction."""

    def estimate(self, node_name: str, model: str | None = None) -> int:
        return NODE_TOKEN_ESTIMATES.get(node_name, 3000)

    def get_model(self, node_name: str) -> str:
        """Return the model name for this node type.

        Respects AGENT_MODEL_* env var overrides, then per-node Settings, then global fallback.
        """
        return _get_per_node_model(node_name)


__all__ = ["NODE_TOKEN_ESTIMATES", "TokenEstimator", "_get_per_node_model"]
