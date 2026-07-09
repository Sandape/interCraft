from __future__ import annotations

from typing import Any

from app.modules.agent_observability.demo_seed import build_strong_debug_demo


def demo_seed_contract(environment: str = "local") -> dict[str, Any]:
    return build_strong_debug_demo(environment=environment)


__all__ = ["demo_seed_contract"]
