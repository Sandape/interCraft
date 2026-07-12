"""Authorization — immutable receipts, effect intents, and execution fencing."""

from app.modules.ai_runtime.authorization.service import (
    AuthorizationError,
    AuthorizationReceipt,
    AuthorizationService,
    issue_authorization_receipt,
    validate_receipt_for_execution,
)

__all__ = [
    "AuthorizationError",
    "AuthorizationReceipt",
    "AuthorizationService",
    "issue_authorization_receipt",
    "validate_receipt_for_execution",
]
