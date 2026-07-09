# Requirements Status: REQ-045 LLM Ops Eval Workflow

Feature status: done

## User Story Status

| Story | Status | Evidence | Notes |
|---|---|---|---|
| US1 Run Trace-Linked Eval Gate | done | [US1 evidence](../../docs/evidence/045-llm-ops-eval-workflow/us1-eval-gate.md) | Local canonical reports, sync modes, mocked LangSmith adapter, and gate exit codes verified. |
| US2 Correlate AI Tasks End To End | done | [US2 evidence](../../docs/evidence/045-llm-ops-eval-workflow/us2-trace-correlation.md) | HTTP, websocket, ARQ, LangGraph, and LLM trace/run propagation verified locally without LangSmith. |
| US3 Enforce Governed External Export | done | [US3 evidence](../../docs/evidence/045-llm-ops-eval-workflow/us3-export-policy.md) | Destination policy, secret guard, LangSmith full-content policy, OTLP downgrade, and export-audit CLI verified. |
| US4 Compare Experiments With Judge Feedback | done | [US4 evidence](../../docs/evidence/045-llm-ops-eval-workflow/us4-experiment-judge.md) | Judge calibration/reporting, experiment comparison CLI/service, AI Ops compare contract, and PM evidence adapter verified. |
| US5 Promote Production Badcases Into Eval Datasets | done | [US5 evidence](../../docs/evidence/045-llm-ops-eval-workflow/us5-badcase-promotion.md) | Governed badcase promotion to candidate/report-only eval cases, CLI/API contracts, and loader lifecycle support verified. |
| US6 Propose Human-Approved Prompt Improvements | done | [US6 evidence](../../docs/evidence/045-llm-ops-eval-workflow/us6-prompt-proposals.md) | Proposal state machine, CLI/API creation, comparison/approval evidence, and no-auto-deploy guardrail verified. |

## Requirement Groups

| Group | Requirements | Status | Evidence | Notes |
|---|---|---|---|---|
| Trace correlation | FR-001..FR-006 | done | [US2 evidence](../../docs/evidence/045-llm-ops-eval-workflow/us2-trace-correlation.md) | OTel-compatible trace identity, run identity, logs, middleware, ARQ metadata, LLM child spans, and coverage summaries are implemented and tested. |
| LangSmith-assisted eval | FR-007..FR-011 | done | [US1 evidence](../../docs/evidence/045-llm-ops-eval-workflow/us1-eval-gate.md), [US3 evidence](../../docs/evidence/045-llm-ops-eval-workflow/us3-export-policy.md) | Local artifacts, mocked sync modes, production export policy, and governed LangSmith sync behavior are implemented and verified. |
| Export governance | FR-012..FR-016 | done | [US3 evidence](../../docs/evidence/045-llm-ops-eval-workflow/us3-export-policy.md) | Production LangSmith full content is governed; generic OTLP is redacted; operational secrets are blocked. |
| Judge evaluation | FR-017..FR-020 | done | [US4 evidence](../../docs/evidence/045-llm-ops-eval-workflow/us4-experiment-judge.md) | Judge is report-only by default; blocking requires calibration or waiver. |
| Experiment comparison | FR-021..FR-023 | done | [US4 evidence](../../docs/evidence/045-llm-ops-eval-workflow/us4-experiment-judge.md) | Baseline/candidate deltas cover quality, cost, latency, recommendation, and risk flags. |
| Badcase feedback loop | FR-024..FR-027 | done | [US5 evidence](../../docs/evidence/045-llm-ops-eval-workflow/us5-badcase-promotion.md) | Candidate/golden promotion requires redaction; report-only is non-blocking; lifecycle metadata is preserved. |
| Prompt improvement | FR-028..FR-030 | done | [US6 evidence](../../docs/evidence/045-llm-ops-eval-workflow/us6-prompt-proposals.md) | Proposals are evidence-backed and cannot auto-deploy. |
| Automation and evidence | FR-031..FR-032 | done | [Focused tests](../../docs/evidence/045-llm-ops-eval-workflow/backend-focused-tests.md), [Chrome E2E](../../docs/evidence/045-llm-ops-eval-workflow/e2e-validation.md) | CLI/automation entry points, quickstarts, OpenAPI notes, focused tests, full-suite audit, and Chrome Control E2E evidence are recorded. |

## Status Rules

- Mark a row `done` only after implementation and verification evidence are
  both linked.
- Use `in_progress` when code exists but verification evidence is incomplete.
- Use `deferred` only when a requirement is explicitly moved to a later REQ.

## Implementation Notes

- 2026-07-05: Phase 1 setup started. Direct LangSmith/OpenTelemetry
  instrumentation dependencies, module entry-point documentation, fixture
  staging, and evidence directory scaffolding are being prepared before
  foundation tests are introduced.
- 2026-07-05: US1 eval gate slice completed with focused tests, REQ-045
  report fixture, disabled/required LangSmith sync modes, and CI workflow
  scaffolding. Real credentialed LangSmith smoke remains optional and is not
  required for the local canonical verdict.
- 2026-07-05: US2 trace correlation slice completed with focused tests across
  runtime tracing config, HTTP middleware, websocket context binding, ARQ
  propagation, AI invocation trace/run persistence, mock LLM spans, and trace
  coverage summary helpers.
- 2026-07-05: US3 export governance slice completed with focused tests for
  destination policy decisions, operational secret blocking, production
  LangSmith full-content authorization, generic OTLP downgrade, and
  `export-audit` CLI output.
- 2026-07-05: US4 experiment/judge slice completed with focused tests for
  judge rubric calibration, report-only/blocking behavior, judge CLI,
  experiment comparison CLI/service, AI Ops compare schema, and PM dashboard
  comparison evidence adapter.
- 2026-07-05: US5 badcase promotion slice completed with focused tests for
  candidate/report-only lifecycle rules, redaction guardrails, DB-free CLI
  automation path, AI Ops promotion contract, and golden loader lifecycle
  preservation.
- 2026-07-05: US6 prompt proposal slice completed with focused tests for
  proposal state transitions, CLI/API creation, comparison/approval evidence,
  rejection metadata, and explicit no-auto-deploy enforcement.
- 2026-07-05: Polish validation completed. REQ-045 focused tests pass
  (75/75). Full backend suite is recorded as blocked by existing REQ-033/035
  collection errors. Chrome Control E2E evidence harness passed.
