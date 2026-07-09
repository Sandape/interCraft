# Requirements Status - 038 LLM Structured Output Hardening

**Feature**: [spec.md](./spec.md)
**Created**: 2026-07-02
**Status**: draft

| Requirement | Status | Implementation Evidence | Verification Evidence | Notes |
|---|---|---|---|---|
| FR-001 Structured/free-form inventory | planned | Pending | Pending | Coverage registry needed. |
| FR-002 Canonical output contracts | planned | Pending | Pending | Pydantic contracts expected during implementation planning. |
| FR-003 Contract-constrained structured output request | planned | Pending | Pending | Provider capability must be confirmed in plan. |
| FR-004 Pre-consumption validation | planned | Pending | Pending | Highest-risk Agent nodes first. |
| FR-005 Remove authoritative free-text extraction | planned | Pending | Pending | Regex/`json.loads` success paths must be migrated. |
| FR-006 Validated object or typed failure | planned | Pending | Pending | Defines the shared client result contract. |
| FR-007 Deterministic fallback behavior | planned | Pending | Pending | Existing fallbacks should become explicit and observable. |
| FR-008 Failure category distinction | planned | Pending | Pending | Schema validation must not appear as generic LLM failure. |
| FR-009 Observability | planned | Pending | Pending | Logs, traces, metrics, eval reports. |
| FR-010 Mock/eval support | planned | Pending | Pending | Include malformed-output fixtures. |
| FR-011 Delegated Agent output enforcement | planned | Pending | Pending | A2A `output_schema` enforcement. |
| FR-012 Local verification check | planned | Pending | Pending | Should fail missing contract or bypassed validation. |
| FR-013 Preserve existing behavior | planned | Pending | Pending | Existing suites remain regression gate. |
| FR-014 Free-form exclusions documented | planned | Pending | Pending | Exclusion list should be explicit. |

## Readiness

- Specify: complete
- Plan: pending
- Tasks: pending
- Implementation: pending
- Verification: pending
