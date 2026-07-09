# 033-eval-pm-dashboard

Automated evaluation and PM Dashboard MVP based on ADR-002.

## Summary

This feature specifies the Safe MVP for LangSmith-assisted eval workflows and a
PM-first data dashboard. It keeps LangSmith Cloud as the eval/trace/experiment
workbench, keeps InterCraft-controlled artifacts as the source of truth, and
freezes production export to metadata plus redacted summaries only.

## Current Status

| Area | Status | Notes |
|---|---|---|
| Spec | draft | Requirements and boundaries captured in `spec.md`. |
| Plan | ready | `plan.md`, `research.md`, `data-model.md`, `contracts/`, and `quickstart.md` created. |
| Tasks | ready | `tasks.md` generated with 142 test-first tasks across 10 user stories. |
| Implementation | not started | This pass intentionally does not modify business code. |
| Requirement status | planned | See `requirements-status.md`. |
| Open questions | resolved | 2026-06-26 clarify session resolved staging payload, nightly budget, approvers, retention, and badcase promotion UI/CLI. |

## Primary Sources

- `docs/decisions/ADR-002-langsmith-eval-workflow-plan.md`
- `specs/026-agent-eval-loop/spec.md`
- `specs/029-otel-langgraph-trace/spec.md`
- `docs/testing/README.md`
- `docs/architecture/source-map.md`

## MVP Boundaries

- LangSmith Cloud is allowed for local/CI/staging eval and experiments.
- Version-controlled golden cases may be uploaded when privacy classification permits.
- Production export is limited to metadata plus redacted summaries.
- PM Dashboard V1 covers user basics, core funnel, AI calls, resume diagnostics,
  mock interview, feedback, badcases, and version fields.
- The user is the initial badcase reviewer and closure owner.
- Production trace export is deferred until redaction, sampling, retention, and review evidence exist.

## Clarified MVP Decisions

- Staging masked prompt/output is allowed only for synthetic, golden, or approved staging test data; other staging traces export metadata plus redacted summaries only.
- Nightly real-model eval budget is about 5M tokens or $50 per night, capped at $1000 per month.
- Baseline refresh and emergency override require dual approval from the PM business owner and technical owner.
- Production trace metadata and redacted summaries are retained for 30 days.
- First-month badcase promotion uses a CLI/documented review flow; admin UI is deferred.

## Task Scope

- Safe MVP first: foundation, redaction policy (US10), version fields (US9), and PR eval gate (US5).
- PM Dashboard MVP next: overview/funnel (US1), resume diagnosis (US2), mock interview (US3), and AI operations (US4).
- LangSmith/debug expansion last: experiment sync (US6) and trace/run drilldown (US7).
