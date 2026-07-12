"""REQ-061 adapters package."""

from app.modules.ai_runtime.adapters.registry import (
    build_acceptance_envelope,
    get_capability_action,
    load_registry,
)
from app.modules.ai_runtime.adapters import (
    error_coach,
    general_coach,
    resume_derive,
    resume_intelligence,
    wechat_agent,
)

__all__ = [
    "build_acceptance_envelope",
    "error_coach",
    "general_coach",
    "get_capability_action",
    "load_registry",
    "resume_derive",
    "resume_intelligence",
    "wechat_agent",
]
