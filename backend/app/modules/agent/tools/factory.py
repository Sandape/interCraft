"""Assemble the production registry from existing InterCraft services."""

from __future__ import annotations

from app.modules.agent.tools.adapters.growth import growth_executors
from app.modules.agent.tools.adapters.interviews import interview_executors
from app.modules.agent.tools.adapters.jobs import job_executors
from app.modules.agent.tools.adapters.resumes import resume_executors
from app.modules.agent.tools.catalog import build_intercraft_registry
from app.modules.agent.tools.registry import ToolRegistry


def build_production_registry() -> ToolRegistry:
    executors = {
        **job_executors(),
        **resume_executors(),
        **interview_executors(),
        **growth_executors(),
    }
    return build_intercraft_registry(executors)


__all__ = ["build_production_registry"]
