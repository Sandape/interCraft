"""REQ-041 US1 — agents utility helpers (token-limit detection, error handler decorators).

This package is the canonical location for cross-cutting agent infrastructure
that does not belong in any single agent's graph or state module.

Per REQ-041 AC matrix FR-001 / FR-002 / FR-003:
- token_limit.py  — is_token_limit_exceeded + MODEL_TOKEN_LIMITS (4 providers)
- node_error_handler.py  — @node_error_handler decorator (deferred to MB2)
- node_error.py  — NodeError Pydantic model (deferred to MB3)
"""