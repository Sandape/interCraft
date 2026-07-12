"""Provider gateway — model policy, routing, circuit breaking, and attempt fencing."""

from app.modules.ai_runtime.provider_gateway.policy_repository import (
    ModelPolicyRecord,
    ModelPolicyRepository,
    PolicyRepositoryError,
    get_default_policy_repository,
    reset_default_policy_repository,
)
from app.modules.ai_runtime.provider_gateway.policy_service import (
    ModelPolicyService,
    PolicyServiceError,
    user_capability_catalog,
)
from app.modules.ai_runtime.provider_gateway.router import (
    LockedPolicySnapshot,
    PolicyRouter,
    PolicyRouterError,
    RouteDecision,
    create_policy_router,
)
from app.modules.ai_runtime.provider_gateway.release_service import (
    GRAY_STAGES,
    GateVerdict,
    ReleaseBatch,
    ReleaseService,
    ReleaseServiceError,
    ReleaseStatus,
    get_release_service,
    reset_release_service,
)
from app.modules.ai_runtime.provider_gateway.service import (
    CircuitBreaker,
    CircuitOpenError,
    ProviderGateway,
    StructuredOutputBoundaryError,
    create_provider_gateway,
    enforce_structured_output,
)

__all__ = [
    "CircuitBreaker",
    "CircuitOpenError",
    "GRAY_STAGES",
    "GateVerdict",
    "LockedPolicySnapshot",
    "ModelPolicyRecord",
    "ModelPolicyRepository",
    "ModelPolicyService",
    "PolicyRepositoryError",
    "PolicyRouter",
    "PolicyRouterError",
    "PolicyServiceError",
    "ProviderGateway",
    "ReleaseBatch",
    "ReleaseService",
    "ReleaseServiceError",
    "ReleaseStatus",
    "RouteDecision",
    "StructuredOutputBoundaryError",
    "create_policy_router",
    "create_provider_gateway",
    "enforce_structured_output",
    "get_default_policy_repository",
    "get_release_service",
    "reset_default_policy_repository",
    "reset_release_service",
    "user_capability_catalog",
]
