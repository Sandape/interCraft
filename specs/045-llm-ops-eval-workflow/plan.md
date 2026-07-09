# Implementation Plan: REQ-045 LLM Ops Eval Workflow

**Branch**: `[045-llm-ops-eval-workflow]` | **Date**: 2026-07-05 | **Spec**: [./spec.md](./spec.md)

**Input**: Feature specification from `specs/045-llm-ops-eval-workflow/spec.md`

## Summary

Deliver the OTel-first, LangSmith-assisted LLM Ops workflow defined by REQ-045.
OpenTelemetry becomes the canonical trace/run correlation substrate for covered
AI workflows, while LangSmith becomes an optional AI workbench for trace
drilldown, datasets, experiments, judge feedback, and prompt/rubric iteration.

The plan keeps local eval artifacts canonical for CI decisions. LangSmith sync,
OTLP export, and production full-content LangSmith export are governed
integration layers: failures are observable but do not change local verdicts or
block end-user AI workflows. Production LangSmith export is explicitly allowed
to include complete unredacted AI payloads, while operational secrets remain
forbidden in all external observability destinations.

Implementation should land in independently testable slices:

1. Trace-linked eval gate with local reports and optional LangSmith sync.
2. End-to-end trace/run correlation across covered AI workflows.
3. Destination-aware export policy, including production full-content
   LangSmith authorization.
4. Judge rubrics, calibration, experiment comparison, badcase promotion, and
   human-reviewed prompt/rubric proposals.

## Technical Context

**Language/Version**: Python >=3.11 backend; TypeScript 5.6 strict frontend.

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 async, Alembic, Redis/ARQ,
structlog, prometheus-client, LangGraph, OpenAI client, OpenTelemetry API/SDK,
OTLP HTTP exporter. Planned additions are a direct backend `langsmith`
dependency and OpenTelemetry instrumentation packages only where they close
verified propagation gaps. The OpenTelemetry Collector is a deployment/runtime
component, not an in-process app dependency.

**Storage**: PostgreSQL for canonical eval, AI invocation, badcase, approval,
policy, and prompt proposal records. Filesystem/CI artifacts remain canonical
for eval reports and evidence under `docs/evidence/`. LangSmith stores synced
datasets, experiments, traces, and feedback as an external workbench. The OTel
Collector or existing observability backend stores generic traces and metrics.

**Testing**: Backend pytest unit, contract, integration, and eval suites; eval
CLI runs through `python -m app.eval.cli`; frontend Vitest/typecheck/build only
for dashboard-facing changes; Playwright E2E for any user-visible admin/PM flow.
LangSmith-enabled behavior must have mocked contract tests plus an opt-in
credentialed smoke path. LangSmith-disabled behavior is mandatory and local.

**Target Platform**: Linux backend/CI deployment, Windows developer workflow,
and current Vite/React frontend. LangSmith production export is supported when
credentials and destination policy are explicitly configured.

**Project Type**: Full-stack web app plus backend library/CLI/automation
workflow.

**Performance Goals**:

- End-user AI workflow overhead from tracing/export preparation: less than 5%
  median added latency on covered workflows, measured without blocking on
  external export.
- Prompt-adjacent PR eval gate: completes within 10 minutes for the planned
  golden/report-only dataset size unless nightly real-model budgets are
  explicitly exhausted.
- LangSmith sync: 95% of successful enabled eval runs appear in LangSmith
  within 2 minutes.
- Failed eval drilldown: report to artifact to trace/LangSmith run in under 3
  minutes for a trained engineer.

**Constraints**:

- Local eval verdicts are canonical; LangSmith sync failures are non-blocking
  integration failures.
- Runtime tracing, metrics, OTLP export, and LangSmith export must fail open for
  end-user AI workflows.
- Production LangSmith full-content export is allowed only through explicit
  destination policy metadata. Secrets, access tokens, credentials, and
  infrastructure passwords are never exportable.
- Metrics labels must use bounded cardinality. Request/user/case-specific
  values belong in traces, logs, reports, or records, not metric labels.
- Judge rubrics are report-only until calibration thresholds or owner waivers
  are recorded.
- Candidate badcases cannot block merges until accepted as golden cases.
- Prompt/rubric proposals cannot auto-deploy or auto-refresh baselines.

**Scale/Scope**:

- Covered AI surfaces before done: interview scoring/reporting, error coaching,
  resume optimization, ability diagnosis, and general coaching.
- This feature extends existing `backend/app/eval/`,
  `backend/app/observability/`, `backend/app/modules/telemetry_contracts/`,
  `backend/app/modules/badcases/`, and PM/admin evidence surfaces. It does not
  create a separate eval platform service.
- Admin console redesign, checkpointer pooling, unrelated agent runtime
  refactors, and automatic prompt deployment are out of scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Library-First | Pass | The plan keeps tracing, eval, export policy, judge rubrics, badcases, and prompt proposals as bounded modules with README/contract expectations. |
| II. CLI Interface | Pass | CLI contracts cover eval run, LangSmith sync, export audit, judge calibration, experiment comparison, badcase promotion, and prompt proposal workflows. |
| III. Test-First | Pass | Contracts and quickstart define tests before implementation: disabled/enabled sync, trace propagation, export policy, judge calibration, experiment comparison, and badcase promotion. |
| IV. Integration & Synchronization Testing | Pass | Cross-boundary tests are required for HTTP/WS/ARQ trace propagation, LangSmith sync, export policy, PM/admin evidence consumption, and CI artifacts. |
| V. Observability | Pass | The feature exists to make AI behavior observable; plan requires structured logs, trace/run IDs, bounded metrics, export status, and failure evidence. |
| Security & Privacy | Pass | Full-content production LangSmith export is allowed by policy, while secrets remain non-exportable and all external destinations require explicit policy decisions. |
| Documentation | Pass | Plan, research, data model, contracts, and quickstart are produced before task generation. |

No unjustified constitution violations are introduced.

## Project Structure

### Documentation (this feature)

```text
specs/045-llm-ops-eval-workflow/
|-- README.md
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- requirements-status.md
|-- contracts/
|   |-- ai-ops-api.md
|   |-- eval-report-schema.md
|   |-- llm-ops-cli.md
|   `-- trace-export-policy.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md                    # Created later by /speckit-tasks
```

### Source Code (planned implementation surface)

```text
backend/app/observability/
|-- tracing.py                  # complete runtime init, propagation, span helpers
|-- langsmith.py                # optional workbench integration or adapter
`-- README.md                   # update contract and fail-open behavior

backend/app/core/
|-- config.py                   # OTel, collector, LangSmith, export policy settings
|-- logging.py                  # trace/span/run identity injection
`-- metrics.py                  # bounded metrics and export/sync counters

backend/app/eval/
|-- cli.py                      # extend run/sync/judge/compare/proposal commands
|-- runner.py                   # trace-linked eval run orchestration
|-- report.py                   # stable local JSON/Markdown report schema
|-- golden_loader.py            # golden/candidate/report-only datasets
|-- judge.py                    # judge rubric execution and calibration
|-- langsmith_sync.py           # optional dataset/experiment/feedback sync
|-- experiment_compare.py       # baseline/candidate comparison
`-- prompt_proposals.py         # human-reviewed prompt/rubric proposals

backend/app/modules/telemetry_contracts/
|-- redaction.py                # keep existing policy helpers; extend to destination policy
|-- retention.py                # destination retention/access metadata
|-- export_policy.py            # planned destination authorization decisions
`-- repository.py               # trace/run reference helpers

backend/app/modules/badcases/
|-- cli.py                      # promotion workflow
|-- service.py
|-- repository.py
`-- schemas.py

backend/app/modules/pm_dashboard/
`-- ...                         # consume eval/experiment/judge/export evidence

backend/app/modules/admin_console/
`-- ...                         # consume AI operations evidence without redesign scope

backend/tests/
|-- contract/
|-- eval/
|-- integration/
`-- unit/

tests/e2e/
`-- 045-*.spec.ts               # only if admin/PM user-visible flows change
```

**Structure Decision**: Extend existing modules instead of creating a new
platform service. `backend/app/eval/` remains the canonical eval workflow;
`backend/app/observability/` remains the OTel runtime boundary;
`backend/app/modules/telemetry_contracts/` owns destination policy and audit;
badcase and PM/admin modules consume these records through contracts.

## Phase Plan

### Phase 0: Research Decisions

- Decide OTel-first trace topology: app spans to collector/fanout, not
  LangSmith-specific tracing as the canonical layer.
- Decide LangSmith role: optional AI workbench for traces, datasets,
  experiments, evaluator feedback, and deep links.
- Decide production export policy: full-content LangSmith is allowed with
  explicit destination policy; secrets are never allowed.
- Decide eval gate semantics: deterministic checks remain canonical blocking
  gates; LangSmith sync is non-blocking.
- Decide judge calibration: report-only until enough human-labeled evidence or
  owner waiver exists.
- Decide experiment comparison and badcase promotion lifecycle.

Output: [research.md](./research.md)

### Phase 1: Design & Contracts

- Define entity model for eval runs, case results, trace refs, LangSmith refs,
  judge rubrics/verdicts, experiment assignments, export policy decisions,
  badcase candidates, and prompt proposals.
- Define CLI contracts for automation and CI.
- Define eval report JSON contract for local artifacts and LangSmith sync input.
- Define trace/export policy contract for OTel, LangSmith, and generic OTLP
  destinations.
- Define dashboard/API contracts for AI Ops evidence consumption.
- Define quickstart validation scenarios for disabled/enabled LangSmith,
  trace correlation, production full-content policy audit, judge calibration,
  experiment comparison, badcase promotion, and prompt proposal guardrails.

Outputs: [data-model.md](./data-model.md), [contracts/](./contracts/),
[quickstart.md](./quickstart.md)

### Phase 2: Task Generation (Later)

Use `/speckit-tasks REQ-045` after this plan to split implementation by user
story. Tasks must preserve TDD order: contract/unit tests first, then minimal
implementation, then integration/E2E evidence and requirements-status updates.

## Post-Design Constitution Re-Check

| Principle | Status | Notes |
|---|---|---|
| I. Library-First | Pass | Artifacts define module boundaries for eval, observability, export policy, badcases, PM/admin evidence, and prompt proposals. |
| II. CLI Interface | Pass | `contracts/llm-ops-cli.md` defines local/CI automation surfaces and exit semantics. |
| III. Test-First | Pass | `quickstart.md` identifies validation commands; contracts define expected outputs before implementation. |
| IV. Integration & Synchronization Testing | Pass | Contracts require trace propagation, LangSmith sync, destination policy, and dashboard/API integration evidence. |
| V. Observability | Pass | Signals map to on-call questions: what ran, where it failed, what it cost, what changed, and whether export/sync succeeded. |
| Security & Privacy | Pass | Destination policy separates full-content LangSmith export from non-approved destinations and forbids operational secrets everywhere. |
| Documentation | Pass | Required planning and design artifacts are present and cross-linked. |

## Complexity Tracking

No constitution violations requiring justification.
