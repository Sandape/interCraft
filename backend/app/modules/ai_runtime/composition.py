"""REQ-061 composition-root factories (T021).

FastAPI, ARQ, CLI and graph runners each call these helpers to assemble a
shared ``ExecutionContext`` without coupling domain code to frameworks.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_runtime.authorization.service import AuthorizationService
from app.modules.ai_runtime.execution_context import (
    ExecutionContext,
    build_execution_context,
)
from app.modules.ai_runtime.provider_gateway.service import (
    ProviderGateway,
    create_provider_gateway,
)
from app.modules.ai_runtime.service import AIRuntimeService


def create_runtime_services(session: AsyncSession) -> dict[str, Any]:
    return {
        "runtime": AIRuntimeService(session),
        "authorization": AuthorizationService(),
        "provider_gateway": create_provider_gateway(session),
    }


def create_api_execution_context(
    session: AsyncSession,
    *,
    root_task_id: UUID,
    task_id: UUID,
    execution_id: UUID,
    user_id: UUID,
    tenant_id: UUID,
    claim_generation: int,
    capability_code: str,
    action_code: str,
    **kwargs: Any,
) -> tuple[ExecutionContext, dict[str, Any]]:
    ctx = build_execution_context(
        root_task_id=root_task_id,
        task_id=task_id,
        execution_id=execution_id,
        user_id=user_id,
        tenant_id=tenant_id,
        claim_generation=claim_generation,
        capability_code=capability_code,
        action_code=action_code,
        session=session,
        **kwargs,
    )
    return ctx, create_runtime_services(session)


def create_worker_execution_context(
    session: AsyncSession,
    **kwargs: Any,
) -> tuple[ExecutionContext, dict[str, Any]]:
    return create_api_execution_context(session, **kwargs)


def create_cli_execution_context(
    session: AsyncSession,
    **kwargs: Any,
) -> tuple[ExecutionContext, dict[str, Any]]:
    return create_api_execution_context(session, **kwargs)


def create_graph_execution_context(
    session: AsyncSession,
    **kwargs: Any,
) -> tuple[ExecutionContext, ProviderGateway, dict[str, Any]]:
    ctx, services = create_api_execution_context(session, **kwargs)
    return ctx, services["provider_gateway"], services


__all__ = [
    "create_api_execution_context",
    "create_cli_execution_context",
    "create_graph_execution_context",
    "create_runtime_services",
    "create_worker_execution_context",
]
