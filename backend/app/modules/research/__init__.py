"""Interview Research module.

REQ-053: Interview Intelligence Engine.

This module is responsible for:
- Scheduling pre-interview research tasks (ARQ cron)
- Executing deep web searches across 4 dimensions
- Generating structured research reports via LLM
- Delivering reports via WeChat (REQ-052) or notification fallback
- Exposing research report APIs for Web viewing

Module layout:
    models.py          # SQLAlchemy models: InterviewResearchTask, InterviewResearchResult
    schemas.py         # Pydantic schemas for API requests/responses
    repository.py      # Data access layer (with RLS enforcement)
    service.py         # Business logic orchestration
    report_generator.py # LLM-based structured report generation
    quality_checker.py # Report content quality validation (FR-018)
    markdown_converter.py # Markdown -> plain text for WeChat
    api.py             # FastAPI router for research endpoints
    cli.py             # CLI commands (trigger-research, research-stats)
"""

__all__ = [
    "models",
    "schemas",
    "repository",
    "service",
    "report_generator",
    "quality_checker",
    "markdown_converter",
    "api",
    "cli",
]