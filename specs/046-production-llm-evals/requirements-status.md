# Requirements Status: REQ-046 Production-Grade LLM Evals

Feature status: active / draft

## User Story Status

| Story | Status | Evidence | Notes |
|---|---|---|---|
| US1 Verify Real LangSmith Experiment Sync | planned | TBD | Move beyond run-level trace upload to Dataset + Experiment + Run + Feedback evidence and clickable URLs. |
| US2 Enforce Production Eval Gates Before Release | planned | TBD | Define production release gates, release-candidate evidence, and waiver rules. |
| US3 Operate Evals With Production SLOs And Alerts | planned | TBD | Add eval health states, scheduled-run freshness, sync health, and operator-visible action items. |
| US4 Govern Production Full-Content Export | planned | TBD | Operationalize full-content LangSmith policy, secret blocks, retention, and access review. |
| US5 Expand High-Risk Eval Coverage | planned | TBD | Cover interview, error coaching, resume optimization, ability diagnosis, and general coaching. |
| US6 Promote Judge Feedback To Production Safely | planned | TBD | Judge stays report-only until calibration, drift, and owner promotion rules are satisfied. |
| US7 Give Operators A Single Production Evidence View | planned | TBD | Join local eval, trace, LangSmith, export policy, coverage, judge, and release decision evidence. |

## Requirement Groups

| Group | Requirements | Status | Evidence | Notes |
|---|---|---|---|---|
| LangSmith production evidence | FR-001..FR-008 | planned | TBD | Requires real Dataset + Experiment + Run + Feedback records and stable URLs. |
| Release gates | FR-009..FR-013 | planned | TBD | Prompt-adjacent gates, release-candidate evidence, waivers, and blocker handling. |
| Eval operations | FR-014..FR-018 | planned | TBD | Health states, alerts, scheduled freshness, sync reliability, and fail-open behavior. |
| Export governance | FR-019..FR-024 | planned | TBD | Full-content LangSmith policy, secret blocking, retention, and access audit. |
| Coverage lifecycle | FR-025..FR-029 | planned | TBD | High-risk surface inventory and badcase-to-dataset lifecycle controls. |
| Judge governance | FR-030..FR-033 | planned | TBD | Calibration, disagreement, drift, suspension, and release-impacting promotion. |
| Operator evidence | FR-034..FR-040 | planned | TBD | Unified evidence view, operation guide, approvals, incidents, and completion evidence. |

## Status Rules

- Mark a row `done` only after implementation and verification evidence are
  both linked.
- Use `in_progress` when code exists but production validation is pending.
- Use `blocked` when an external dependency, credential, workspace access, or
  unresolved policy decision prevents validation.
- Use `deferred` only when a requirement is explicitly moved to a later REQ.

## Initial Baseline Notes

- 2026-07-05: REQ-045 is complete as the foundation. Local eval gate,
  OTel-first correlation, export policy, run-level LangSmith sync, Judge,
  experiment comparison, badcase promotion, prompt proposals, and operation
  guide evidence exist.
- 2026-07-05: A real LangSmith screenshot confirms run-level trace sync in the
  `intercraft-prod` project, but not yet a complete Dataset + Experiment +
  Evaluation Results workflow. REQ-046 starts from that gap.
- 2026-07-05: v1.0.0 production freeze was accepted separately in
  `docs/acceptance/v1-production-freeze.md`. This freeze verified real
  Chrome-controlled resume v2 editing, persistence, and real LLM analysis, but
  it does not complete any REQ-046 user story. Keep REQ-046 rows `planned`
  until their own implementation and evidence are linked here.
