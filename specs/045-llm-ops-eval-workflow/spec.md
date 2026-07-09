# Feature Specification: LLM Ops Eval Workflow

**Feature Branch**: `[045-llm-ops-eval-workflow]`

**Created**: 2026-07-05

**Status**: Draft

**Input**: User description: "Research the current code implementation, assess the gap against the ideal OTel-first, LangSmith-assisted eval workflow, and organize it into a new REQ through /speckit-specify. Grill me if anything is uncertain."

## Relationship To Existing Specs

This requirement consolidates the unfinished LLM Ops workflow scope that is
currently spread across REQ-026 Agent Eval-Driven Self-Improvement Loop,
REQ-029 OpenTelemetry & LangGraph Distributed Trace, REQ-033 Eval + PM
Dashboard V1, and the LangSmith portion of REQ-043 Agent Production Refactor.

REQ-045 does not supersede REQ-044 Admin Console Redesign. The admin console
may consume the outcomes of this requirement, but its information architecture
and visual redesign are out of scope here.

REQ-045 also excludes checkpointer pooling, graph runtime refactoring unrelated
to observability or evaluation, and automatic prompt deployment. Prompt
improvement proposals may be generated and compared, but humans remain the
approval authority.

## Current Baseline And Gap Assessment

The current system has meaningful foundations:

- A golden eval runner exists for selected interview scoring and reporting
  cases, with deterministic Chinese fidelity checks and CI-friendly reports.
- Trace identifiers, artifact references, and LangSmith URL fields already
  exist in eval report contracts, with `"unavailable"` fallback behavior.
- OpenTelemetry helper utilities, span decorators, and optional OTLP export
  support exist, and many graph nodes are already marked for tracing.
- Redaction and retention policies exist for telemetry contracts.
- PM/admin dashboard surfaces already include version, experiment, AI
  operations, badcase, and trace-oriented concepts.

The gap to the ideal workflow is still large enough to require a dedicated
requirement:

- Runtime trace correlation is incomplete. AI task traces, logs, LLM invocation
  records, eval case results, HTTP requests, background jobs, and websocket
  sessions are not yet guaranteed to share one canonical trace/run identity.
- The LangSmith integration is not yet a production workflow. The system has
  a LangSmith exporter skeleton and report placeholders, but no complete
  dataset/experiment sync, no stable deep links, and no verified
  OTLP-compatible fanout path.
- Evaluation coverage is narrow. Current golden cases focus on a small
  interview slice, while high-risk agent graphs, retrieval/tool behavior,
  multi-turn state, production badcases, and experiment comparisons are not yet
  first-class eval targets.
- LLM-as-Judge is not yet part of the eval loop. Deterministic checks are
  valuable, but subjective answer quality, coaching usefulness, groundedness,
  and agent task success require calibrated judge rubrics and human review.
- Privacy policy exists as local logic, but external export governance is not
  yet enforced as a mandatory pre-export workflow for LangSmith or OTLP traces.
- Dashboard version fields exist, but A/B attribution and prompt/model/rubric
  comparison are not yet backed by a complete experiment assignment and eval
  evidence loop.

Desired end state: OpenTelemetry is the company-wide observability substrate
for trace correlation, system health, and generic monitoring. LangSmith is an
optional AI workbench layered on top for LLM debugging, datasets, experiments,
judge feedback, and prompt iteration. Local eval artifacts remain canonical;
LangSmith enriches analysis but does not become the sole source of truth.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run Trace-Linked Eval Gate (Priority: P1)

As an engineer changing prompts, rubrics, models, or agent behavior, I want a
repeatable eval gate that produces local artifacts and, when enabled, links each
case to the matching trace and LangSmith run so I can debug failures without
guesswork.

**Why this priority**: This is the smallest valuable slice of the workflow. It
turns the existing eval runner from a pass/fail artifact into a debuggable
quality gate while preserving local operation when LangSmith is unavailable.

**Independent Test**: Can be tested by running the eval suite with LangSmith
disabled and enabled, then verifying that the local report is complete in both
modes and that enabled runs contain matching trace/run/deep-link identifiers.

**Acceptance Scenarios**:

1. **Given** LangSmith is disabled, **When** an eval suite runs, **Then** the
   suite produces the same local verdict, stable JSON/Markdown reports, and
   `"unavailable"` LangSmith links without network dependency.
2. **Given** LangSmith is enabled and credentials are valid, **When** an eval
   suite runs, **Then** every case result includes a stable case id, run id,
   trace id when available, artifact reference, and LangSmith deep link.
3. **Given** a prompt or rubric change introduces a known regression, **When**
   the eval gate runs, **Then** the gate blocks the change and the failure report
   links to the trace, prompt fingerprint, rubric version, and failure reason.
4. **Given** LangSmith export fails during a run, **When** the local eval verdict
   is computed, **Then** the local verdict is preserved and the export failure is
   reported as a non-blocking integration failure.

---

### User Story 2 - Correlate AI Tasks End To End (Priority: P1)

As an on-call engineer or product engineer, I want one canonical trace/run
identity for each AI task across request handling, graph nodes, tools, LLM
calls, logs, metrics, and persisted invocation records so I can investigate
latency, cost, and quality issues quickly.

**Why this priority**: LangSmith-assisted evaluation is only useful when the
trace data is trustworthy. Without end-to-end correlation, reports and
dashboards cannot explain what actually happened.

**Independent Test**: Can be tested by executing a covered AI workflow and
asserting that the same trace/run identifiers appear in the task report, logs,
LLM invocation record, graph span sequence, and eval artifact.

**Acceptance Scenarios**:

1. **Given** a covered AI workflow is started through an API request, **When**
   the workflow calls graph nodes, tools, and LLMs, **Then** all emitted
   observability records share the same canonical trace/run identity.
2. **Given** a covered AI workflow continues through streaming or background
   processing, **When** later steps emit logs or eval artifacts, **Then** the
   original trace/run identity is preserved.
3. **Given** an AI task fails mid-workflow, **When** the failure is reported,
   **Then** the report still contains enough trace/run information to inspect
   the last successful node, failed node, latency, model, token usage, and error
   class.

---

### User Story 3 - Enforce Governed External Export (Priority: P1)

As a product owner responsible for user data, I want any external trace or eval
export to pass through a clear destination-aware authorization, retention, and
sampling policy so LangSmith and OTLP export can be useful while production
full-content LangSmith export remains explicit, auditable, and access-controlled.

**Why this priority**: The ideal layered architecture is not acceptable unless
external export is intentional and governed. Production may send complete
unredacted AI payloads to LangSmith, but that must be an approved full-content
destination policy rather than an accidental side effect.

**Independent Test**: Can be tested with seeded sensitive payloads and a dry-run
export audit that proves each destination receives the representation allowed by
policy: full-content payloads for approved production LangSmith export, redacted
or metadata-only payloads for destinations that are not approved for full
content, and blocked export when the policy is missing or invalid.

**Acceptance Scenarios**:

1. **Given** a payload contains resume text, job descriptions, interview free
   text, LLM inputs, LLM outputs, credentials, or user identifiers, **When** it
   is prepared for external export, **Then** the exported representation follows
   the active destination policy and records whether the decision was
   full-content, redacted, metadata-only, or blocked.
2. **Given** production LangSmith full-content export is explicitly enabled,
   **When** traces or eval artifacts are sent to LangSmith, **Then** complete
   unredacted AI payloads are allowed and the export records destination,
   environment, owner, policy version, access scope, and retention metadata.
3. **Given** an external destination is not approved for full-content export,
   **When** the same traces or eval artifacts are exported, **Then** raw user AI
   payloads are redacted, summarized, or blocked according to policy.
4. **Given** the export policy audit fails or required approval metadata is
   missing, **When** export is attempted, **Then** the external export is blocked
   while the local workflow continues and records the reason.

---

### User Story 4 - Compare Experiments With Judge Feedback (Priority: P2)

As a PM or AI engineer, I want to compare baseline and candidate prompts,
models, rubrics, or agent versions using deterministic metrics plus calibrated
LLM-as-Judge feedback so I can make iteration decisions with evidence.

**Why this priority**: After traces and export are reliable, experiment
comparison is what turns observability into product improvement.

**Independent Test**: Can be tested by running a baseline and candidate against
the same dataset, producing a comparison report with deterministic metrics,
judge scores, confidence flags, and human-review status.

**Acceptance Scenarios**:

1. **Given** a baseline and candidate version are evaluated on the same dataset,
   **When** the comparison completes, **Then** the report shows pass rates,
   known regression recall, judge score deltas, cost, latency, and confidence
   warnings.
2. **Given** a judge rubric has not reached calibration thresholds, **When** the
   comparison report is produced, **Then** judge feedback is marked report-only
   and does not block merges by itself.
3. **Given** a judge rubric is calibrated against human labels, **When** it is
   used in an eval run, **Then** the report records judge version, rubric
   version, agreement evidence, and any disagreement cases for review.

---

### User Story 5 - Promote Production Badcases Into Eval Datasets (Priority: P2)

As a quality owner, I want production or staging failures to become redacted
candidate eval cases with trace context and human approval so the golden
dataset evolves from real usage without becoming noisy or unsafe.

**Why this priority**: The system already has badcase and PM dashboard
concepts. Connecting them to eval datasets closes the feedback loop from
production quality issues back into regression protection.

**Independent Test**: Can be tested by promoting a seeded badcase into a
candidate golden case, verifying redaction, approval, trace linkage, and
exclusion from blocking gates until accepted.

**Acceptance Scenarios**:

1. **Given** a production badcase is selected for promotion, **When** the owner
   creates a candidate eval case, **Then** the candidate carries source trace,
   artifact, redaction audit, owner, and review status.
2. **Given** a candidate case has not been approved, **When** blocking evals run,
   **Then** the candidate may appear in report-only datasets but cannot block
   merges as a golden case.
3. **Given** a candidate case is approved, **When** it becomes golden, **Then**
   future eval reports reference the original badcase and trace context.

---

### User Story 6 - Propose Human-Approved Prompt Improvements (Priority: P3)

As an AI engineer, I want the system to propose prompt or rubric improvements
from failed evals and judge feedback, then compare candidates before any human
applies them.

**Why this priority**: This is the self-improvement layer. It should come after
the trace, eval, governance, and experiment foundations are reliable.

**Independent Test**: Can be tested by feeding failed cases into the proposal
workflow, generating a candidate prompt or rubric, and verifying it remains a
proposal until explicitly accepted by a human.

**Acceptance Scenarios**:

1. **Given** recurring eval failures share a pattern, **When** the proposal
   workflow runs, **Then** it produces a candidate prompt or rubric change with
   linked evidence and expected impact.
2. **Given** a candidate improvement exists, **When** it is evaluated against
   baseline datasets, **Then** the comparison report shows quality, cost,
   latency, and regression risk before approval.
3. **Given** no human has approved the candidate, **When** deployment or baseline
   promotion is attempted, **Then** the system prevents automatic application.

---

### Edge Cases

- LangSmith credentials are absent, invalid, rate-limited, or revoked.
- OTLP or LangSmith export is slow, unavailable, or partially successful.
- Trace context is missing at workflow entry but downstream components still
  need a generated correlation identity.
- A workflow crosses API, websocket, and background execution boundaries.
- Streaming LLM calls emit partial output before failing.
- The same user request triggers multiple agent subgraphs or retry attempts.
- Eval artifacts reference a trace that has expired due to retention policy.
- Redaction removes content required for debugging, requiring a safe summary.
- Judge verdicts disagree with deterministic checks or human labels.
- Experiment assignment is missing, malformed, or ambiguous.
- A candidate prompt improves one graph while regressing another.
- Production badcases contain user-deleted or policy-restricted content.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST treat OpenTelemetry-compatible trace identity as the
  canonical observability correlation layer for covered AI workflows.
- **FR-002**: System MUST assign or preserve a stable run identity for each
  covered AI task and connect it to trace identity, eval case results, logs,
  metrics, and persisted AI invocation records.
- **FR-003**: System MUST preserve trace/run correlation across request,
  websocket, background job, graph node, tool, and LLM call boundaries for
  covered workflows.
- **FR-004**: System MUST record model, provider, latency, token usage, cache
  behavior, prompt fingerprint, rubric version, graph, node, and error class
  where applicable for covered LLM calls.
- **FR-005**: System MUST fail open for end-user AI workflows when tracing,
  metrics, OTLP export, or LangSmith export is unavailable.
- **FR-006**: System MUST make missing trace, artifact, or LangSmith references
  explicit with stable unavailable values rather than omitting fields.
- **FR-007**: System MUST provide local eval artifacts that are complete enough
  to diagnose pass/fail outcomes without requiring LangSmith access.
- **FR-008**: System MUST support optional LangSmith dataset and experiment sync
  for eval runs.
- **FR-009**: System MUST associate LangSmith experiment runs with local eval
  run ids, case ids, trace ids when available, prompt fingerprints, rubric
  versions, model versions, and source revisions.
- **FR-010**: System MUST support a generic OTLP-compatible export path for AI
  traces and MUST keep LangSmith-specific enrichment optional.
- **FR-011**: System MUST report LangSmith export status separately from local
  eval pass/fail status.
- **FR-012**: System MUST block external export when the active destination
  policy cannot authorize or produce an allowed representation.
- **FR-013**: System MUST support environment-aware and destination-aware export
  policies, including an explicitly enabled production LangSmith full-content
  policy that allows complete unredacted AI payloads.
- **FR-014**: System MUST record export policy decisions for exported eval
  cases, traces, and badcase-derived artifacts, including destination,
  representation level, policy version, owner, and decision reason.
- **FR-015**: System MUST never export application secrets, credentials, access
  tokens, or infrastructure passwords to external observability destinations;
  raw resumes, job descriptions, interview free text, LLM inputs, and LLM
  outputs are allowed only under an approved full-content LangSmith policy.
- **FR-016**: System MUST enforce destination retention and access-control
  metadata for exported trace and eval references and clearly indicate when
  linked traces have expired or are access-restricted.
- **FR-017**: System MUST maintain deterministic eval checks as the primary
  blocking gate until judge rubrics have passed calibration.
- **FR-018**: System MUST support LLM-as-Judge rubrics for answer quality,
  groundedness, coaching usefulness, task success, and policy compliance.
- **FR-019**: System MUST record judge model, judge version, rubric version,
  prompt, score, rationale summary, confidence, and disagreement markers for
  each judge verdict.
- **FR-020**: System MUST require human-labeled calibration evidence before a
  judge rubric can become merge-blocking.
- **FR-021**: System MUST support baseline-versus-candidate comparisons for
  prompts, rubrics, models, agent versions, and dataset versions.
- **FR-022**: System MUST propagate experiment id, variant, dataset version, and
  source revision through eval reports and PM/admin evidence surfaces.
- **FR-023**: System MUST show quality, regression, cost, latency, and confidence
  deltas in experiment comparison outputs.
- **FR-024**: System MUST distinguish golden, candidate, report-only, deprecated,
  and rejected eval cases.
- **FR-025**: System MUST allow production or staging badcases to be promoted
  into candidate eval cases only after redaction and human approval metadata are
  recorded.
- **FR-026**: System MUST link promoted eval cases back to their source badcase,
  trace, artifact, owner, approval decision, and promotion date.
- **FR-027**: System MUST prevent candidate cases from blocking merges until
  they are explicitly accepted as golden cases.
- **FR-028**: System MUST support prompt and rubric improvement proposals based
  on eval failures, judge feedback, and badcase clusters.
- **FR-029**: System MUST keep prompt and rubric improvements as human-reviewed
  proposals until explicitly accepted.
- **FR-030**: System MUST compare proposed improvements against baseline before
  they can be promoted.
- **FR-031**: System MUST expose enough CLI or automation entry points to run
  evals, sync enabled LangSmith experiments, audit export payloads, compare
  experiments, and record approvals.
- **FR-032**: System MUST provide requirement-level evidence for each completed
  user story, including local reports, trace correlation proof, redaction audit
  output, and LangSmith-disabled behavior.

### Key Entities *(include if feature involves data)*

- **EvalRun**: A complete evaluation execution, including suite, environment,
  source revision, dataset version, prompt fingerprint, rubric version, model
  version, status, budget usage, and export status.
- **EvalCaseResult**: One case outcome within an eval run, including case id,
  graph/node target, pass/fail status, deterministic metrics, judge verdicts,
  trace/run references, artifact references, and failure reasons.
- **TraceRunRef**: The correlation envelope connecting trace id, run id, case
  id, artifact reference, and optional LangSmith deep link.
- **LangSmithExperimentRef**: The optional external workbench reference for a
  synced dataset, experiment, run, or feedback record.
- **JudgeRubric**: A versioned scoring definition for subjective AI quality
  dimensions, including calibration status and human-label evidence.
- **JudgeVerdict**: A single judge evaluation result, including score, rationale
  summary, confidence, judge identity, rubric version, and disagreement markers.
- **ExperimentAssignment**: The baseline or candidate variant context attached
  to eval runs, AI tasks, dashboard views, and badcase evidence.
- **AIInvocationRecord**: A persisted representation of an LLM call with
  provider, model, latency, token usage, cache behavior, prompt fingerprint,
  trace/run identity, and quality attribution fields.
- **ExportPolicyDecision**: The representation, sampling, retention, access
  scope, and destination decision made before any external trace or eval export.
- **BadcasePromotionCandidate**: A redacted candidate eval case derived from a
  production or staging issue, with owner approval and source trace context.
- **PromptImprovementProposal**: A candidate prompt or rubric change generated
  from evidence, linked to comparison results and human approval state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of covered eval case results include case id, run id,
  dataset version, prompt fingerprint, rubric version, model version, source
  revision, artifact reference, and explicit trace/LangSmith availability.
- **SC-002**: With LangSmith disabled, the eval gate completes without network
  dependency and produces identical local pass/fail verdicts to LangSmith-enabled
  mode for the same inputs.
- **SC-003**: With LangSmith enabled in a configured environment, at least 95%
  of successful eval runs appear in LangSmith within 2 minutes with matching
  local run ids, source revisions, and export policy decisions.
- **SC-004**: For covered AI workflows, at least 95% of successful LLM invocation
  records contain non-empty trace/run correlation and can be matched to logs and
  eval artifacts.
- **SC-005**: Known deterministic regressions in golden cases block the eval
  gate with a non-zero exit and an actionable failure report.
- **SC-006**: Judge rubrics remain report-only until they have at least 30
  human-labeled calibration examples and at least 80% agreement on the target
  decision boundary, or an explicit owner waiver is recorded.
- **SC-007**: External export audit over seeded sensitive payloads proves that
  production LangSmith full-content export includes approved raw AI payloads
  with policy metadata, while all non-approved destinations contain zero raw
  resumes, raw job descriptions, raw interview free text, credentials, access
  tokens, or secrets.
- **SC-008**: A PM or AI engineer can compare baseline versus candidate quality,
  regression, cost, latency, and judge-feedback deltas from one report or
  dashboard view within 5 minutes of an eval run completing.
- **SC-009**: A failed eval case can be traced from report to local artifact to
  trace/run details and, when enabled, LangSmith run details in under 3 minutes.
- **SC-010**: Failure of OTLP or LangSmith export never blocks an end-user AI
  task and never changes the local eval pass/fail verdict.
- **SC-011**: At least five high-risk AI surfaces have golden or report-only
  eval coverage before the feature is marked done: interview scoring/reporting,
  error coaching, resume optimization, ability diagnosis, and general coaching.
- **SC-012**: 100% of production/staging badcase promotions require redaction
  audit output and human approval metadata before becoming candidate eval cases.
- **SC-013**: 100% of production full-content LangSmith exports include
  destination, environment, owner, access scope, retention, policy version, and
  full-content authorization metadata.

## Assumptions

- LangSmith is allowed for local, CI, staging, and production workflows when
  credentials and destination policy are explicitly configured.
- Production LangSmith export is allowed to include complete unredacted AI
  payloads, including resumes, job descriptions, interview free text, LLM
  inputs, and LLM outputs.
- Complete unredacted AI payload export does not include application secrets,
  credentials, access tokens, or infrastructure passwords.
- Local eval reports and repository-managed datasets remain the canonical
  source of truth for CI decisions.
- LangSmith is an assisted debugging and evaluation workbench, not the only
  storage location for eval results.
- OpenTelemetry-compatible trace identity is the primary cross-system
  correlation standard.
- Existing admin and PM dashboard surfaces can consume the new evidence fields;
  redesigning those surfaces is out of scope.
- Existing deterministic eval checks remain valuable and are not replaced by
  LLM-as-Judge scoring.
- Automatic prompt deployment and automatic baseline refresh are out of scope;
  all prompt/rubric changes require human approval.
- This requirement intentionally focuses on observability, eval, LangSmith
  integration, experiment comparison, privacy governance, and feedback loops.
  Checkpointer stability and unrelated agent runtime refactors belong to other
  requirements.
