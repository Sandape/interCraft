# Agent Observability Module

REQ-035 ownership module for trace-first AI and agent debugging.

This module owns:

- Trace, span, payload, LLM call, tool operation, eval-link, coverage-gap, and
  retention read models.
- Redacted and masked payload visibility policy.
- Safe LLM cURL reconstruction.
- Fail-open capture helpers for centralized Agent/LLM entry points.
- Admin observability API endpoints under
  `/api/v1/admin-console/observability`.

The module must never store or return live API keys, bearer tokens, cookies, or
private service credentials.
