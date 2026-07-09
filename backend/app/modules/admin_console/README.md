# Admin Console Module

REQ-035 ownership module for the internal management console.

This module owns:

- Admin-console capability resolution and access-boundary dependencies.
- Read-only admin API endpoints under `/api/v1/admin-console`.
- Dashboard summary and privacy-safe snapshot orchestration.
- Append-only audit-event helpers for admin access, dashboard reads, payload
  reveals, cURL views, and snapshot generation.

The module intentionally does not own the underlying product metrics,
observability capture, or eval runner logic. Those stay in `pm_dashboard`,
`agent_observability`, and `eval` respectively.
