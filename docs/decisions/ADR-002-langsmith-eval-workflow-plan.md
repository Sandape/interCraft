# ADR-002: LangSmith-Assisted Agent Evaluation Workflow Plan

## Status

Accepted For MVP Planning

## Date

2026-06-26

## Context

InterCraft already has the beginnings of an agent quality and observability
system:

- Feature 026 provides a local golden-case eval suite under
  `backend/app/eval/` and `backend/tests/eval/`.
- Feature 029 provides an OpenTelemetry tracing skeleton under
  `backend/app/observability/`.
- `backend/app/agents/llm_client.py` records token usage, retries, latency,
  audit rows, and Prometheus metrics.
- `specs/026-agent-eval-loop/golden/` contains the first version-controlled
  golden dataset for interview score/report nodes.

The goal is to add a durable workflow that helps two audiences:

1. Developers and coding agents need faster debug, regression detection, and
   acceptance evidence during prompt and agent changes.
2. PM and leadership need repeatable reports on AI quality, cost, reliability,
   and delivery readiness.

LangSmith is a good fit for trace inspection, datasets, experiments, online and
offline evaluation, and CI-friendly reporting. It should not become the sole
source of truth for user quota, billing, compliance records, or product
analytics.

Official references used for this plan:

- LangSmith evaluation: <https://docs.langchain.com/langsmith/evaluation>
- LangSmith pytest integration: <https://docs.langchain.com/langsmith/pytest>
- LangSmith OpenTelemetry tracing:
  <https://docs.langchain.com/langsmith/trace-with-opentelemetry>
- LangSmith online evaluations:
  <https://docs.langchain.com/langsmith/online-evaluations>
- OpenTelemetry GenAI semantic conventions:
  <https://opentelemetry.io/docs/specs/semconv/gen-ai/>

## Decision

Adopt an **OTel-first, LangSmith-assisted** evaluation workflow:

1. Keep OpenTelemetry as the instrumentation standard and portability layer.
2. Use LangSmith as the developer-facing trace, dataset, experiment, and eval
   workbench.
3. Keep canonical facts in InterCraft-controlled storage:
   `ai_messages`, quota usage, Prometheus metrics, eval JSON reports, CI
   artifacts, and feature evidence under `docs/evidence/`.
4. Automate collection, scoring, CI gating, and report generation.
5. Require human review for data governance, baseline changes, production trace
   promotion, and prompt optimization approval.

## MVP Requirements Freeze

These requirements are fixed for the first detailed implementation plan. They
come from the product-owner answers on 2026-06-26 and should not be reopened
unless the user explicitly changes them.

| ID | Requirement | Decision |
|---|---|---|
| MVP-R001 | LangSmith deployment mode | Use **LangSmith Cloud** for the first POC/MVP. |
| MVP-R002 | Golden-case upload | Upload version-controlled golden cases to LangSmith is allowed. |
| MVP-R003 | Production payload policy | Production data may be exported only as **metadata + redacted summaries**; raw resumes, interview answers, JD text, and free-form chat are out of MVP production export scope. |
| MVP-R004 | First dashboard audience | The first data dashboard is optimized for **PM usage**, not developer debugging or executive reporting. |
| MVP-R005 | Badcase review owner | The user is the initial human reviewer and approval owner for badcase classification, promotion, and closure. |
| MVP-R006 | First dashboard metric scope | Prioritize the consultant report's first-priority metrics: user basics, core funnel, AI calls, resume diagnostics, interview flow, user feedback, badcase, and version fields. |
| MVP-R007 | LangSmith role | LangSmith is used for eval experiments, datasets, feedback, and trace drill-down; it is not the canonical product analytics or billing ledger. |
| MVP-R008 | Production rollout | Production trace export remains deferred until redaction, sampling, and review evidence exist; MVP can ship with local/CI/staging LangSmith integration only. |

### PM Dashboard V1 Scope

The first dashboard should answer PM questions quickly:

1. Are users entering and completing the core job-seeker journey?
2. Which funnel step loses the most users?
3. Are resume diagnostics leading to viewed reports and accepted suggestions?
4. Are users starting and completing mock interviews?
5. Are AI calls reliable, affordable, and tied to prompt/model versions?
6. What badcases are open, fixed, or recurring?

Dashboard V1 should include these panels:

| Panel | Metrics |
|---|---|
| Product overview | UV, registered users, active users, completed AI tasks, AI success rate, total token/cost, open badcases |
| Core funnel | visit/login/register -> resume upload/create -> diagnosis success -> report view -> suggestion accept -> interview complete -> feedback view |
| Resume center | diagnosis count, suggestions shown, suggestions accepted, report views, score delta |
| Mock interview | starts, completions, average question count, report views, retries |
| AI operations | model, prompt version, token usage, estimated cost, latency, success/failure, retry count |
| Feedback and badcase | thumbs up/down, helpfulness score, text feedback count, badcase type/status/fix result |
| Version and experiment | app version, prompt version, rubric version, experiment id/group, release stage |

Out of scope for Dashboard V1: payment conversion, ARPU, K-factor, advanced
AI-human agreement, full security dashboard, and recommendation quality.

## Non-Goals

- Do not upload all raw production user content by default.
- Do not replace existing OTel, structlog, Prometheus, or audit tables.
- Do not make LangSmith the quota or billing source of truth.
- Do not allow automatic prompt optimization to deploy to production.
- Do not block ordinary non-agent PRs on expensive real-model evaluation.

## Human Review Boundaries

These require the user, owner, or designated reviewer:

| Area | Human responsibility | Why automation stops |
|---|---|---|
| LangSmith workspace | Create workspace, choose Cloud vs self-hosted, configure billing | Codex cannot own vendor account or legal commitments |
| Secrets | Add `LANGSMITH_API_KEY`, endpoint, project names, CI secrets | Codex should not invent or expose credentials |
| Data policy | Decide which inputs/outputs may leave the system, retention window, masking rules | User resumes and interview answers can contain sensitive data |
| Golden labels | Approve expected answers, score ranges, and qualitative rubrics | LLM-generated labels can normalize bad behavior |
| Baseline refresh | Sign off new baseline metrics and threshold changes | Prevents regressions from becoming the new normal |
| Merge override | Approve emergency merge when eval gate fails | Business risk decision |
| Production trace promotion | Review redaction and case quality before adding to golden dataset | Production data can contain PII and ambiguous outcomes |
| Prompt optimization | Review candidate prompt diffs before rollout | Metrics can improve while product quality or policy fit worsens |
| PM/BOSS report wording | Approve external-facing summaries and risk framing | Reports influence stakeholder decisions |

For MVP, several boundaries are now resolved:

- LangSmith workspace mode: LangSmith Cloud.
- Golden-case upload: allowed.
- Production data export: metadata and redacted summaries only.
- First dashboard audience: PM.
- Initial badcase reviewer: the user.

## Codex Capability Boundaries

Codex can:

- Implement the LangSmith integration code and keep it behind feature flags.
- Add OTel span attributes and propagation tests.
- Extend the eval runner, pytest suite, and CLI.
- Add GitHub Actions jobs and report artifacts.
- Generate Markdown/JSON/HTML reports from eval, trace, cost, and test data.
- Add redaction utilities and tests for known PII classes.
- Maintain versioned golden cases and mark stale cases during schema drift.
- Produce prompt optimization candidates and eval comparisons.

Codex cannot:

- Create or pay for external accounts.
- Provide legal/compliance approval for user data export.
- Guarantee LLM evaluator correctness or deterministic outputs.
- Guarantee LangSmith service uptime, pricing stability, or future API behavior.
- Validate production behavior without access to production data and secrets.
- Decide whether a metric regression is acceptable for business reasons.

## Implementation Plan

### Cross-Cutting Implementation Contracts

These contracts apply to every phase. They are intentionally explicit because
most eval and observability failures come from unclear ownership of identifiers,
payloads, thresholds, and artifacts.

#### Required identifiers

Every eval run, trace, report, and promoted case should carry these fields:

| Field | Purpose | Source |
|---|---|---|
| `run_id` | Joins local report, CI artifact, and LangSmith experiment | Generated once per eval/report run |
| `git_sha` | Ties behavior to source state | `git rev-parse --short HEAD` or CI env |
| `branch` | Helps compare PR vs main | CI env or git |
| `prompt_fingerprint` | Detects prompt changes even when node name is stable | Hash of prompt text + tool descriptions |
| `model` | Explains quality/cost changes | LLM client response/config |
| `graph` | Groups agent behavior | Agent graph name |
| `node` | Localizes failures | Node wrapper / golden case |
| `case_id` | Joins golden dataset and result | Golden case JSON |
| `schema_version` | Handles state shape drift | Golden case/report schema |
| `trace_id` | Joins logs, spans, reports, and A2A messages | OTel context |

#### Data classification

| Class | Examples | Default handling |
|---|---|---|
| Public metadata | graph, node, model, git SHA, duration, token counts | Safe to export |
| Internal metadata | user id hash, thread id hash, prompt fingerprint, error category | Export after hashing or normalization |
| Sensitive user content | resume text, interview answers, JD text, free-form chat | Do not export raw in production by default |
| Secrets | access token, refresh token, API keys, passwords, JWT secret | Never export or persist in reports |
| Derived summaries | failure reason, evaluator verdict, redacted snippet | Export if generated by approved redaction path |

#### Environment policy

| Environment | LangSmith usage | Payload policy | Gate behavior |
|---|---|---|---|
| `local` | Optional | Developer-controlled; prefer synthetic/golden data | No merge gate |
| `ci` | Optional after secrets exist | Golden data only | Blocks prompt-adjacent PRs on deterministic failures |
| `staging` | Recommended after Phase 3 | Masked traces; raw payload only if approved | Non-blocking report unless release candidate |
| `production` | Deferred until policy approval | Sampled metadata + redacted summaries by default | Never blocks runtime; export must fail open |

#### LangSmith naming

Use stable names so reports remain searchable:

- Project: `intercraft-{env}`
- Dataset: `intercraft-{graph}-{node}-golden-v{schema_version}`
- Experiment: `{run_id}-{branch}-{git_sha}`
- Trace metadata tags: `env`, `graph`, `node`, `user_hash`, `thread_hash`,
  `prompt_fingerprint`, `case_id` when from eval.

#### Gate thresholds

Initial thresholds should be conservative:

| Metric | PR mock gate | Nightly real-model gate | Notes |
|---|---:|---:|---|
| active case pass rate | 100% | Report-only until baseline stabilizes | Mock failures are deterministic regressions |
| known regression recall | 100% | 100% | The Chinese-fidelity regression cases must stay caught |
| stale case count | Report-only | Report-only | Stale cases should create tasks, not block unrelated work |
| token cost delta | Report-only | Alert if above approved budget | Real-model cost is noisy |
| latency delta | Report-only | Alert on sustained regression | Needs trend data |
| production error trace export | Never runtime-blocking | Never runtime-blocking | Observability must fail open |

#### Required artifacts

Each milestone should produce these artifacts:

| Artifact | Location | Required by |
|---|---|---|
| Eval JSON | `docs/evidence/<run>/eval-report.json` or CI artifact | Developers, trend jobs |
| Markdown report | `docs/evidence/<run>/eval-report.md` | PM/dev review |
| LangSmith run link | Markdown report metadata | Debug workflow |
| Redaction audit sample | `docs/evidence/<run>/redaction-check.md` | Human review |
| Baseline file | Future `specs/026-agent-eval-loop/baselines/` | Gate comparison |
| Override record | Future `docs/evidence/<run>/override.md` | Audit |

#### Rollback and disable switches

All integration must be disable-first:

- `LANGSMITH_TRACING=false` disables LangSmith reporting.
- OTel exporter failure must drop spans or fall back to local/console export.
- CI eval upload failure should not fail the deterministic local eval result.
- Production runtime must never depend on LangSmith availability.
- Prompt optimization candidates must remain files/proposals until reviewed.

#### Definition of ready for implementation

Before coding a phase, confirm:

- [ ] Human review boundary for that phase is resolved or explicitly deferred.
- [ ] Required secrets and environment variables are available or mocked.
- [ ] Payload policy for the target environment is written down.
- [ ] Acceptance criteria can be tested locally or in CI.
- [ ] Rollback/disable switch exists before external calls are enabled.

#### Definition of done for implementation

A phase is done only when:

- [ ] Local tests pass.
- [ ] Existing non-eval regressions are checked with the relevant project
  command.
- [ ] At least one happy-path artifact and one failure-path artifact exist.
- [ ] Human review items are either signed off or listed as blockers.
- [ ] The plan or feature status is updated with evidence links.

### Phase 0: Governance And Scope Freeze

**Goal:** Decide the minimum safe data policy before any external upload.

**Tasks**

- [x] Choose LangSmith Cloud vs self-hosted: MVP uses LangSmith Cloud.
- [ ] Define environments: `local`, `ci`, `staging`, `production`.
- [ ] Define trace payload policy per environment:
  - local/ci: synthetic or golden data only
  - staging: 100% trace allowed after masking
  - production: sampled metadata and redacted summaries only
- [ ] Define retention and deletion expectations.
- [ ] Define cost budget for nightly real-model eval.

**Human review:** Required before Phase 1 if any data leaves local/CI.

**Estimated effort:** 0.5-1 day, mostly human/product/security decision time.

### Phase 1: Local And CI Eval Gate MVP

**Goal:** Make the existing feature 026 eval suite reliable as a PR gate before
adding vendor dependency.

**Tasks**

- [ ] Add a dedicated CI job for `cd backend && uv run pytest tests/eval -q`.
- [ ] Add path filters so prompt/agent/eval changes trigger the gate.
- [ ] Make `backend/app/eval/cli.py --report-out` produce a stable JSON report.
- [ ] Add a small report renderer that turns eval JSON into Markdown for CI
  artifacts.
- [ ] Record `git_sha`, model, prompt version/fingerprint, graph, node, case id,
  and schema version in every report.

**Acceptance criteria**

- [ ] Prompt-adjacent PRs run eval automatically.
- [ ] CI artifact shows per-case failures and aggregate pass rate.
- [ ] Non-agent PRs are not slowed down by unnecessary real-model eval.

**Estimated effort:** 1-2 development days.

**Codex fit:** High. This is mostly local code, tests, and CI wiring.

### Phase 2: LangSmith Offline Experiments

**Goal:** Mirror local golden-case evals into LangSmith datasets and experiments.

**Tasks**

- [ ] Add explicit `langsmith` dependency to `backend/pyproject.toml` if still
  only present transitively in `uv.lock`.
- [ ] Add LangSmith env handling:
  `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`,
  `LANGSMITH_ENDPOINT`.
- [ ] Add an optional LangSmith reporter module beside `backend/app/eval/`.
- [ ] Sync version-controlled golden cases to a named LangSmith dataset.
- [ ] Attach evaluator outputs as feedback: pass/fail, Chinese fidelity,
  score-range verdict, expected-contains verdict, token/cost when available.
- [ ] Keep local JSON as canonical fallback when LangSmith is disabled.

**Acceptance criteria**

- [ ] `LANGSMITH_TRACING=false` runs exactly like today.
- [ ] With credentials, eval runs appear as LangSmith experiments.
- [ ] Local JSON and LangSmith results share the same run id and git SHA.

**Human review:** Required for API key and project/workspace selection.

**Estimated effort:** 2-4 development days.

**Codex fit:** High, after secrets are provided by the user.

### Phase 3: OTel Trace Completion For Agent Debug

**Goal:** Make LangSmith traces useful enough for debugging failed eval and
staging agent runs.

**Tasks**

- [ ] Wrap `LLMClient.invoke` and `invoke_stream` in OTel spans.
- [ ] Add GenAI-compatible span attributes for model, provider, tokens, latency,
  retry count, cache status, graph, node, user scope, and thread id.
- [ ] Stop creating unrelated random `request_id` values inside LLM logs; reuse
  current request/trace context.
- [ ] Propagate trace context across HTTP, WebSocket, LangGraph subgraphs, and
  ARQ task boundaries.
- [ ] Add tool-call spans for Tavily and any future tools.
- [ ] Add redaction/masking before span export.
- [ ] Add integration tests using the in-memory exporter.

**Acceptance criteria**

- [ ] One interview run produces one trace containing node, LLM, and tool spans.
- [ ] Logs include the same trace id as the trace backend.
- [ ] Export failure is fail-open and does not break agent execution.
- [ ] PII redaction tests cover email, phone, access token, refresh token,
  resume text sample, and free-form answer sample.

**Human review:** Required for production sampling and raw payload policy.

**Estimated effort:** 3-6 development days for staging-quality tracing; more if
all graph/worker boundaries need production-hardening at once.

**Codex fit:** Medium-high. Code is straightforward, but cross-boundary context
propagation needs careful integration testing.

### Phase 4: Reports For Developers, PM, And Leadership

**Goal:** Convert eval and telemetry data into repeatable deliverables.

**Tasks**

- [ ] Define PM Dashboard V1 report/template first:
  - product overview
  - core funnel
  - resume center
  - mock interview
  - AI operations
  - feedback and badcase
  - version and experiment
- [ ] Define later report templates:
  - developer acceptance report
  - AI quality and cost weekly report
  - PM/BOSS delivery readiness report
- [ ] Build a report generator that consumes eval JSON, LangSmith run links,
  local metrics, CI status, and evidence paths.
- [ ] Store generated reports under `docs/evidence/<run-or-feature>/`.
- [ ] Include links to LangSmith runs when available, but keep reports readable
  without external access.
- [ ] Add trend fields: pass rate, failing nodes, token cost, retry rate,
  cache hit rate, trace sample count, known risks, recommended action.

**Acceptance criteria**

- [ ] One command generates a report from the latest eval artifacts.
- [ ] Report contains enough context for a PM/BOSS review without opening code.
- [ ] Report clearly distinguishes verified facts, sampled observations, and
  inferred risks.

**Human review:** Required before sharing outside the engineering team.

**Estimated effort:** 2-4 development days for static reports; longer for a
dashboard.

**Codex fit:** High for Markdown/HTML reports. Medium for dashboards if product
design is needed.

### Phase 5: Production Sampling And Trace Promotion

**Goal:** Improve the golden dataset from real behavior without leaking data or
automatically trusting production traces.

**Tasks**

- [ ] Capture feedback signals: retry, abandonment, low score, explicit thumbs
  if later added.
- [ ] Sample production traces based on error, low quality, retry, or reviewer
  request.
- [ ] Add a candidate generator that converts a trace into a golden-case draft.
- [ ] Run redaction before draft creation.
- [ ] Add review metadata: reviewer, reason, source trace id, redaction status.
  The initial reviewer is the user.
- [ ] Add accepted cases to `specs/026-agent-eval-loop/golden/` or future graph
  golden directories.

**Acceptance criteria**

- [ ] No production trace enters the version-controlled golden dataset without
  review.
- [ ] Every promoted case links back to source trace metadata without exposing
  raw PII.
- [ ] Stale or ambiguous candidates can be rejected with a reason.

**Human review:** Mandatory.

**Estimated effort:** 1-2 weeks depending on frontend/admin workflow needs.

**Codex fit:** Medium. The backend workflow is feasible; case quality still
requires humans.

### Phase 6: Prompt Optimization Candidates

**Goal:** Let automation propose improvements, not deploy them.

**Tasks**

- [ ] Add a command to compare baseline prompt vs candidate prompt across
  golden cases.
- [ ] Generate prompt diffs and metric deltas.
- [ ] Store prompt proposals as review artifacts.
- [ ] Require approval before applying prompt changes.

**Acceptance criteria**

- [ ] Candidate prompt output includes baseline/candidate metrics and diff.
- [ ] No code path auto-applies a candidate prompt to production.
- [ ] Rejected candidates retain rejection reason for future learning.

**Human review:** Mandatory.

**Estimated effort:** 3-7 development days for candidate comparison; more if
introducing DSPy or another optimizer.

**Codex fit:** Medium. Evaluation orchestration is doable; judging product fit
is human work.

## Overall Timeline

| Scope | Phases | Estimated duration | Notes |
|---|---:|---:|---|
| Safe MVP | 0-2 | 4-7 working days | Local CI gate + LangSmith offline experiments |
| Useful debug workflow | 0-3 | 1.5-2.5 weeks | Adds real traces and trace links |
| Stakeholder reporting | 0-4 | 2-3 weeks | Adds repeatable reports |
| Production learning loop | 0-5 | 3-5 weeks | Adds reviewed trace promotion |
| Optimization loop | 0-6 | 4-6+ weeks | Depends on dataset size and reviewer bandwidth |

These estimates assume one coding agent working with periodic human review.
The schedule expands if production data policy, self-hosting, or dashboard UI is
required early.

## Pain Points And Unavoidable Defects

| Issue | Impact | Mitigation |
|---|---|---|
| LLM eval is nondeterministic | Real-model scores can fluctuate across runs | Use mock PR gate, nightly real eval, repeated samples for important metrics |
| Golden cases drift as state schema changes | False failures or skipped cases | Add `schema_version`, stale status, and loader warnings |
| Small golden dataset overfits | Metrics look good while product quality is weak | Expand per graph/node, include promoted production cases after review |
| SaaS data export risk | PII/compliance exposure | OTel-first redaction, environment policy, production sampling, self-host option |
| Vendor lock-in | LangSmith-specific APIs can be costly to replace | Keep local JSON and OTel as canonical integration points |
| CI runtime and cost | Real eval can slow PRs and burn quota | PR mock eval, nightly real eval, path filters, budgets |
| Reports can overclaim certainty | PM/BOSS may read sampled data as ground truth | Label facts vs samples vs inference in every report |
| Trace links can break or expire | Reports lose context over time | Store local summary and evidence even when LangSmith link expires |
| Automatic prompt optimization can game metrics | Worse product behavior despite higher eval score | Human approval and qualitative review before merge |
| Production sampling misses rare issues | Trace set may not represent all failures | Always sample errors, low scores, retries, and explicit reports at 100% |

Some defects are unavoidable: no LLM eval can be perfectly objective, no trace
backend can prove unobserved behavior, and no automated report can replace a
reviewer's judgment on whether a regression is acceptable.

## Fast-Iteration Compatibility

This workflow should support rapid code and prompt iteration by design:

- Every eval run records `git_sha`, prompt fingerprint, model, graph, node, and
  case schema version.
- PRs use fast mock evaluation; expensive real-model evaluation runs on demand
  or nightly.
- Path filters prevent unrelated UI or documentation changes from paying agent
  eval cost.
- Golden cases can be `active`, `stale`, or `superseded` instead of being
  deleted during schema churn.
- Baselines are frozen and only refreshed through review.
- Reports are generated from artifacts, not from live-only dashboards.
- LangSmith is optional at runtime; local JSON reports remain valid if the
  vendor is unavailable.
- Prompt changes should include prompt fingerprint changes and at least one
  affected eval artifact.

## Suggested First Milestone

Build the **Safe MVP**:

1. Phase 0 remaining decisions: environment policy details, secret ownership,
   retention, and nightly real-model budget. Cloud/self-host, golden upload,
   production redacted-only policy, PM dashboard audience, and badcase reviewer
   are already fixed.
2. Phase 1 local CI eval gate with report artifacts.
3. Phase 2 optional LangSmith upload for CI/staging experiments only.
4. PM Dashboard V1 requirements and data contract for first-priority metrics.

Stop before production tracing until the data policy is approved. This gives
developers immediate regression protection and gives PM/BOSS an initial report
format without taking on production privacy risk.

## Alternatives Considered

### LangSmith as the single system of record

- Pros: Simple mental model and good developer UX.
- Cons: Creates vendor lock-in and moves quota, cost, and potentially sensitive
  product facts outside InterCraft-controlled storage.
- Decision: Rejected. LangSmith is a workbench, not the canonical ledger.

### Pure self-hosted OTel stack only

- Pros: Maximum control over data and vendor independence.
- Cons: Much slower to build LangGraph-friendly eval, dataset, annotation, and
  experiment workflows.
- Decision: Rejected for the first milestone. Keep OTel as the portability layer
  while using LangSmith for high-leverage workflow UX.

### Fully automated prompt optimization and deployment

- Pros: Fast iteration and potentially lower manual effort.
- Cons: Optimizers can overfit small datasets, game metrics, or remove product
  nuance that humans care about.
- Decision: Rejected. Automation may propose; humans approve.

### Production raw trace upload by default

- Pros: Maximum debugging fidelity.
- Cons: Unacceptable privacy and compliance risk for resumes, interview
  answers, and free-form career data.
- Decision: Rejected. Production starts with sampled metadata and redacted
  summaries unless a stricter data review approves more.

## Resolved Questions

1. First POC deployment: **LangSmith Cloud**.
2. Golden case upload: **allowed**.
3. Production data policy: **metadata + redacted summaries only**.
4. First dashboard audience: **PM**.
5. Initial badcase human reviewer: **the user**.

## Remaining Open Questions

1. Are raw prompts and outputs allowed in staging traces after masking, or only
   summaries and metadata?
2. What is the nightly real-model eval budget in tokens or currency?
3. Who can approve baseline refreshes and emergency eval overrides? The badcase
   owner is fixed, but release-gate authority is still separate.
4. Should production trace retention be 7, 14, or 30 days?
5. Do we need an admin UI for trace promotion, or is a CLI-reviewed workflow
   enough for the first month?

## Consequences

- Developers get a concrete eval gate before adding more vendor dependency.
- LangSmith adds high-value inspection and experiment UX without replacing
  InterCraft's source-of-truth data.
- The workflow remains portable because OTel and local JSON artifacts are kept.
- More human process is required around baselines and production data, but that
  is intentional risk control rather than overhead.
