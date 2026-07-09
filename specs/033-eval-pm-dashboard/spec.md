# Feature Specification: Automated Eval & PM Dashboard MVP

**Feature Branch**: `[033-eval-pm-dashboard]`

**Created**: 2026-06-26

**Status**: Draft

**Input**: User description: "基于 ADR-002 和已冻结 MVP 需求，为自动化评测与 PM 数据看板 MVP 创建/细化 SpecKit feature spec；本次只做需求划分与规格化，不写实现代码。"

## Clarifications

### Session 2026-06-26

- Q: Staging payload policy: after masking, may staging send raw prompt/output to LangSmith, or only metadata plus redacted summaries? -> A: Staging may send masked prompt/output only for synthetic, golden, or approved staging test data; otherwise metadata plus redacted summaries only.
- Q: Nightly real-model eval budget: what token or currency budget is allowed per nightly run and per month? -> A: Medium budget: each nightly run may use up to about 5M tokens or $50, with a monthly cap of $1000.
- Q: Baseline refresh and emergency override approval: who can approve a new baseline or override a failing eval gate? -> A: Both require dual approval from the PM business owner and technical owner.
- Q: Production trace retention: should production trace metadata/redacted-summary retention be 7, 14, or 30 days? -> A: 30 days.
- Q: Badcase promotion workflow: does MVP need an admin UI, or is a CLI/documented review workflow enough for the first month? -> A: First month uses CLI/documented review flow; admin UI is deferred.

## Scope

### In Scope

- Use LangSmith Cloud as the first POC/MVP workbench for eval, trace inspection, datasets, feedback, and experiments.
- Allow version-controlled golden cases to be uploaded to LangSmith datasets and synced to LangSmith experiments.
- Keep InterCraft-controlled data, local eval reports, product analytics, quota usage, and cost accounting as the canonical sources of truth.
- Provide PM Dashboard V1 for product usage and quality review, covering user basics, core funnel, AI calls, resume diagnostics, mock interviews, user feedback, badcases, and version fields.
- Support the initial badcase human review workflow where the user is the first reviewer, classifier, promotion approver, and closure owner; first-month promotion uses a CLI/documented review flow and defers admin UI.
- Define version, prompt, rubric, run, trace, and experiment fields so PM metrics, eval results, and debug traces can be joined.
- Define environment-specific data export policies, with production limited to metadata plus redacted summaries, production trace retention fixed at 30 days, and production trace export deferred until redaction, sampling, and review evidence exist.
- Define local, CI, nightly, and staging eval workflows for PR gates, reports, and LangSmith experiment sync.

### Non-Goals

- Do not upload raw production resumes, interview answers, job descriptions, or free-form text to LangSmith in MVP production scope.
- Do not make LangSmith the sole product analytics, billing, quota, cost, compliance, or audit ledger.
- Do not replace existing local eval JSON, evidence files, structured logs, metrics, or OpenTelemetry-oriented tracing.
- Do not build an executive dashboard, payment dashboard, ARPU/K-factor analysis, security dashboard, or full recommendation-quality system in Dashboard V1.
- Do not deploy automatic prompt optimization or automatic baseline refresh without human approval.
- Do not block ordinary non-agent PRs on expensive real-model evaluation.
- Do not enable production trace export until the privacy evidence, sampling policy, and human review checklist are complete.
- Do not require an admin UI for badcase-to-golden-case promotion during the first MVP month.

## User Scenarios & Testing

### User Story 1 - PM Views Product Overview And Core Funnel (Priority: P1)

As a PM, I want a dashboard that shows the core job-seeker funnel from visit or login through resume diagnosis, report view, suggestion acceptance, mock interview completion, and feedback view, so that I can quickly see where users are progressing or dropping off.

**Why this priority**: This is the primary PM value of Dashboard V1 and anchors the rest of the metrics. Without the funnel, downstream AI quality and badcase metrics lack product context.

**Independent Test**: Can be tested by loading a seeded metric period and confirming the dashboard shows product overview counts, funnel steps, conversion rates, and drop-off deltas without opening developer tooling.

**Acceptance Scenarios**:

1. **Given** a PM opens Dashboard V1 for a selected date range, **When** product usage exists, **Then** the dashboard shows UV, registered users, active users, completed AI tasks, AI success rate, total token/cost estimate, and open badcases.
2. **Given** funnel events exist for the date range, **When** the PM views the funnel, **Then** each step shows count, conversion rate from the previous step, conversion rate from entry, and largest drop-off indicator.
3. **Given** no events exist for a selected range, **When** the PM views the dashboard, **Then** the dashboard shows zero-state metrics with the selected filters and does not imply missing telemetry is a product failure.

---

### User Story 2 - PM Reviews Resume Diagnosis And Suggestion Adoption (Priority: P1)

As a PM, I want to see how often users run resume diagnostics, view reports, receive suggestions, and accept suggestions, so that I can judge whether resume AI output is leading to visible user action.

**Why this priority**: Resume diagnosis is one of InterCraft's core AI value loops. PM needs adoption and outcome metrics before deeper model-quality analysis.

**Independent Test**: Can be tested by feeding sample diagnosis and suggestion events and verifying diagnosis count, report views, suggestions shown, suggestions accepted, acceptance rate, and score delta are displayed.

**Acceptance Scenarios**:

1. **Given** resume diagnostics were requested and completed, **When** the PM opens the resume panel, **Then** the panel shows diagnosis count, success/failure rate, report views, suggestions shown, and suggestions accepted.
2. **Given** a diagnosis has before/after scoring data, **When** the PM inspects the period summary, **Then** the dashboard shows score delta using a documented metric definition.
3. **Given** suggestions are shown but never accepted, **When** the PM filters by prompt version or rubric version, **Then** the dashboard highlights the low adoption segment without exposing raw resume content.

---

### User Story 3 - PM Reviews Mock Interview Usage And Completion (Priority: P1)

As a PM, I want to see mock interview starts, completions, average question count, report views, retries, and completion rate, so that I can understand whether the interview workflow is useful and finishable.

**Why this priority**: Mock interview is a core product loop and a major source of AI calls. Its completion and retry behavior helps PM distinguish UX issues from AI quality issues.

**Independent Test**: Can be tested by loading seeded interview sessions with starts, abandoned sessions, completions, reports, and retries, then verifying the dashboard aggregates them correctly.

**Acceptance Scenarios**:

1. **Given** users started mock interviews, **When** the PM views the interview panel, **Then** the panel shows starts, completions, completion rate, average question count, report views, and retry count.
2. **Given** a version segment has high starts but low completions, **When** the PM filters by app version or prompt version, **Then** the drop-off remains visible with the selected version context.
3. **Given** an interview run fails before report generation, **When** the PM views interview outcomes, **Then** the failure contributes to AI/product health metrics without revealing raw interview answers.

---

### User Story 4 - PM Reviews AI Cost, Latency, And Reliability (Priority: P1)

As a PM, I want to see AI call volume, estimated cost, token usage, latency, success/failure rate, retry count, model, and prompt version, so that I can connect product value to AI operating cost and reliability.

**Why this priority**: PM needs cost and reliability visibility before scaling AI usage. This story also prevents LangSmith from becoming the cost ledger by defining dashboard-facing canonical metrics.

**Independent Test**: Can be tested by loading AI invocation summaries and confirming aggregate and segmented metrics match the documented definitions.

**Acceptance Scenarios**:

1. **Given** AI invocations occurred in the selected period, **When** the PM opens AI operations, **Then** the dashboard shows call count, success rate, failure rate, retry count, p50/p95 latency, token usage, estimated cost, model, and prompt version.
2. **Given** one prompt version has higher failure or cost than the baseline, **When** the PM filters by prompt version, **Then** the dashboard shows the segment delta and links to related eval or experiment metadata when available.
3. **Given** LangSmith is unavailable, **When** the PM opens the dashboard, **Then** canonical local product metrics still render and LangSmith-only drill-down links are marked unavailable.

---

### User Story 5 - Developer Runs Golden-Case Eval Automatically In PR (Priority: P1)

As a developer, when I open a PR that changes prompt-adjacent or agent-eval-adjacent behavior, I want golden-case eval to run automatically, so that known regressions are caught before merge.

**Why this priority**: This is the core regression-protection value inherited from feature 026 and ADR-002 Safe MVP.

**Independent Test**: Can be tested by creating a PR-like change to an eval-triggering file and confirming the PR eval report is produced with per-case verdicts and an aggregate pass/fail result.

**Acceptance Scenarios**:

1. **Given** a PR changes a prompt, rubric, graph node behavior, golden case, or eval runner configuration, **When** CI runs, **Then** the golden-case eval suite runs and publishes a report artifact.
2. **Given** a deterministic golden case fails, **When** the gate completes, **Then** the report identifies case id, graph, node, prompt version or fingerprint, rubric version, run id, and failure reason.
3. **Given** a PR does not affect AI or eval behavior, **When** CI runs, **Then** the expensive eval path is not required for merge.
4. **Given** a failing eval gate needs an emergency override, **When** override is requested, **Then** both the PM business owner and technical owner must approve with reason and evidence before merge proceeds.

---

### User Story 6 - Developer Syncs Eval Results To LangSmith Experiment (Priority: P2)

As a developer, I want eval results and golden-case runs to sync to LangSmith experiments when credentials and flags are present, so that I can inspect runs in LangSmith while local JSON remains the canonical artifact.

**Why this priority**: LangSmith improves inspection and experiment UX, but MVP must remain useful without vendor access. P2 because local CI eval is the P1 safety net.

**Independent Test**: Can be tested by running an eval with LangSmith enabled and verifying the local report and LangSmith experiment share the same run id, git SHA, case ids, and aggregate verdicts.

**Acceptance Scenarios**:

1. **Given** LangSmith credentials and project configuration are available, **When** golden-case eval completes, **Then** results are visible as a LangSmith experiment with matching run id and git SHA.
2. **Given** LangSmith upload fails after local eval completes, **When** the CI report is generated, **Then** local eval pass/fail remains authoritative and upload failure is reported separately.
3. **Given** a golden dataset schema version changes, **When** cases are synced, **Then** the dataset name or metadata distinguishes the schema version.

---

### User Story 7 - Developer Locates Failed Case By Trace Or Run ID (Priority: P2)

As a developer, when an eval case or staging run fails, I want the report to include run_id, trace_id, case_id, and LangSmith link when available, so that I can jump from summary to the exact failing case.

**Why this priority**: Debug speed depends on stable join fields across local artifacts, traces, experiments, and logs. P2 because it amplifies US5 and US6.

**Independent Test**: Can be tested by creating one failing golden case and confirming the generated report contains enough identifiers to locate the corresponding local artifact and LangSmith run.

**Acceptance Scenarios**:

1. **Given** a golden case fails in CI, **When** the developer opens the report, **Then** it includes run_id, case_id, graph, node, prompt fingerprint, rubric version, trace_id when present, and local artifact path.
2. **Given** the failed run was synced to LangSmith, **When** the developer follows the experiment link, **Then** the LangSmith view can be matched back to the local case by run_id and case_id.
3. **Given** no trace is available for a failure, **When** the report is generated, **Then** it states trace unavailable rather than inventing a trace link.

---

### User Story 8 - Reviewer Marks, Classifies, And Closes Badcases (Priority: P1)

As the initial human reviewer, I want to mark a badcase, classify it, attach eval or trace evidence, and close it with a resolution, so that AI and product quality issues have accountable follow-through.

**Why this priority**: ADR-002 freezes the user as initial badcase review owner. Without a review lifecycle, production or staging failures cannot safely become golden cases or closed learning loops.

**Independent Test**: Can be tested by creating a sample badcase, classifying it, linking evidence, changing status, and closing it with a required resolution reason.

**Acceptance Scenarios**:

1. **Given** a reviewer finds an AI or product issue, **When** they create a badcase, **Then** the badcase records type, severity, source, status, reviewer, run_id or trace_id when available, and privacy classification.
2. **Given** a badcase has been fixed or rejected, **When** the reviewer closes it, **Then** closure requires a resolution category, evidence link or rationale, reviewer identity, and timestamp.
3. **Given** a badcase is considered for golden-case promotion, **When** promotion is requested, **Then** human approval and redaction status are required before the case is accepted.
4. **Given** the MVP is within its first month, **When** a reviewer promotes a badcase into a golden-case candidate, **Then** the documented CLI/review flow is sufficient and no admin UI is required.

---

### User Story 9 - System Retains Version, Prompt, Rubric, And Experiment Fields (Priority: P1)

As a PM or developer, I want product metrics, eval results, badcases, and AI calls to carry consistent version fields, so that regressions can be attributed to app releases, prompt changes, rubric changes, experiments, or environments.

**Why this priority**: Without consistent version context, dashboard trends and eval failures are hard to interpret. This is a foundational data-contract story.

**Independent Test**: Can be tested by inspecting generated metric rows, eval results, and badcases and confirming required version fields are present or explicitly marked unknown.

**Acceptance Scenarios**:

1. **Given** an AI call, eval run, or badcase is recorded, **When** the record is stored or exported, **Then** it includes app version, release stage, prompt version or fingerprint, rubric version, model, environment, and experiment id/group when applicable.
2. **Given** a version field is unavailable, **When** metrics are generated, **Then** the field is set to an explicit unknown value and counted in data-quality metrics.
3. **Given** PM filters by a version field, **When** matching records exist, **Then** all dashboard panels apply the same filter semantics.

---

### User Story 10 - System Enforces Environment-Specific Redaction Policy (Priority: P1)

As the system owner, I want data export behavior to differ by environment, with production limited to metadata plus redacted summaries, so that MVP can use LangSmith safely without leaking sensitive career data.

**Why this priority**: Privacy and data governance are hard blockers for production usage. This story makes production export deferred until evidence exists and prevents accidental raw-content upload.

**Independent Test**: Can be tested by running export/redaction policy checks for local, CI, staging, and production sample payloads and confirming forbidden raw content is blocked in production.

**Acceptance Scenarios**:

1. **Given** production data contains resume text, interview answers, job description text, or free-form chat, **When** an export to LangSmith or an external report is attempted, **Then** only metadata plus approved redacted summary is allowed.
2. **Given** local or CI eval uses synthetic or version-controlled golden data, **When** LangSmith upload is enabled, **Then** upload is allowed if the case privacy classification permits it.
3. **Given** a staging trace uses synthetic, golden, or approved staging test data, **When** masked prompt/output export is configured, **Then** export is allowed after redaction passes; all other staging traces export only metadata plus redacted summaries.
4. **Given** redaction or export fails in production, **When** runtime continues, **Then** product execution is not blocked and the export failure is recorded for review.

### Edge Cases

- LangSmith is unavailable or credentials are missing: local eval and PM dashboard metrics still work; LangSmith sync is skipped or marked failed without changing canonical results.
- A golden case contains sensitive or user-derived content: upload is blocked unless the case is explicitly approved, redacted, version-controlled, and classified as uploadable.
- A production trace accidentally includes raw sensitive content in a summary field: export is blocked and the redaction failure becomes a badcase or privacy review item.
- Eval budget is exhausted during nightly real-model runs: the run is marked incomplete; partial results are report-only and cannot refresh baselines; the medium budget is capped at about 5M tokens or $50 per night and $1000 per month.
- A prompt version is missing from older records: records remain queryable under `unknown`, and data-quality metrics show the missing-field rate.
- A badcase is duplicated across feedback, eval, and trace sources: records can be linked to one canonical badcase without losing source-specific evidence.
- A dashboard metric has delayed ingestion: the dashboard shows freshness and last-successful-update time so PM does not treat stale data as current.
- A reviewer disagrees with an automated badcase classification: human classification wins and the automated label remains as non-authoritative evidence.
- Staging policy changes from summary-only to masked prompt/output: the policy version must be recorded so old and new traces are not mixed silently.
- A LangSmith experiment link expires or permissions change: local summary and evidence remain readable without external access.

## Requirements

### Functional Requirements

**PM Dashboard V1**

- **FR-001**: System MUST provide a PM Dashboard V1 oriented around product usage, AI quality, AI operations, feedback, badcases, and version context.
- **FR-002**: Dashboard V1 MUST include product overview metrics: UV, registered users, active users, completed AI tasks, AI success rate, total token usage, estimated cost, and open badcases.
- **FR-003**: Dashboard V1 MUST include a core funnel from visit/login/register through resume creation or upload, diagnosis success, report view, suggestion acceptance, interview completion, and feedback view.
- **FR-004**: Dashboard V1 MUST include resume diagnosis metrics: diagnosis count, report views, suggestions shown, suggestions accepted, acceptance rate, success/failure rate, and score delta when available.
- **FR-005**: Dashboard V1 MUST include mock interview metrics: starts, completions, completion rate, average question count, report views, retries, and failure rate.
- **FR-006**: Dashboard V1 MUST include AI operation metrics: model, prompt version or fingerprint, token usage, estimated cost, latency, success/failure, retry count, and cache-related fields when available.
- **FR-007**: Dashboard V1 MUST include feedback and badcase metrics: thumbs up/down or equivalent feedback, helpfulness score when available, text feedback count, badcase type, status, severity, source, and fix result.
- **FR-008**: Dashboard V1 MUST include version and experiment filters: app version, release stage, environment, prompt version or fingerprint, rubric version, experiment id/group, model, graph, and node.
- **FR-009**: Dashboard V1 MUST show metric definitions, selected filters, and data freshness for each panel so PM can distinguish current facts from stale or missing data.

**LangSmith eval and experiment workflow**

- **FR-010**: System MUST use LangSmith Cloud for the first MVP workbench when LangSmith integration is enabled.
- **FR-011**: System MUST allow version-controlled golden cases to be uploaded to LangSmith datasets when the case privacy classification permits upload.
- **FR-012**: System MUST sync eval results to LangSmith experiments when credentials and enablement flags are present.
- **FR-013**: System MUST keep local eval JSON/report artifacts as canonical even when LangSmith sync succeeds.
- **FR-014**: System MUST record one stable run_id for each eval run and use it across local reports, CI artifacts, LangSmith experiments, and badcase references.
- **FR-015**: System MUST include git SHA or source revision, branch, graph, node, case_id, schema_version, prompt version or fingerprint, rubric version, model, environment, and run timestamp in every eval report.
- **FR-016**: System MUST expose failed eval cases with enough metadata to locate matching trace or LangSmith run when available.
- **FR-017**: LangSmith integration MUST fail open for product runtime and MUST NOT turn LangSmith availability into a product dependency.

**PR, nightly, and staging eval flow**

- **FR-018**: Prompt-adjacent, rubric-adjacent, agent-node, eval-runner, and golden-case changes MUST trigger golden-case eval in PR.
- **FR-019**: PR eval MUST publish per-case verdicts, aggregate pass rate, known regression recall, stale case count, and links or identifiers for debug artifacts.
- **FR-020**: PR eval MUST block deterministic failures for prompt-adjacent changes unless a documented human override is recorded.
- **FR-021**: Non-agent changes MUST NOT be required to run expensive real-model eval as a merge gate.
- **FR-022**: Nightly eval MUST be able to run real-model or higher-fidelity checks as report-only within the approved medium budget of about 5M tokens or $50 per night and $1000 per month; baseline changes require dual approval under FR-024.
- **FR-023**: Staging eval and trace workflows MUST be non-blocking by default unless a release-candidate policy explicitly promotes them to a gate.
- **FR-024**: Baseline refresh and emergency override MUST require dual approval from the PM business owner and technical owner, with reason, evidence, timestamp, and affected baseline or gate recorded.

**Badcase human review**

- **FR-025**: System MUST support badcase creation from eval failure, staging trace, user feedback, PM review, or manual reviewer entry.
- **FR-026**: Each badcase MUST capture type, severity, source, status, reviewer, created time, last updated time, environment, privacy class, run_id or trace_id when available, and linked evidence.
- **FR-027**: Badcase statuses MUST support at least open, triaged, in_progress, awaiting_validation, closed, and rejected.
- **FR-028**: Badcase classification MUST support at least resume diagnosis quality, mock interview quality, AI reliability, AI cost/latency, product funnel/UX, data quality, privacy/redaction, and eval regression.
- **FR-029**: Closing a badcase MUST require reviewer identity, closure reason, fix result or rejection reason, and evidence or rationale.
- **FR-030**: Promoting a badcase into a golden-case candidate MUST require human approval, redaction status, source trace/run metadata, and version context.
- **FR-030a**: During the first MVP month, badcase promotion MUST be supported through a CLI/documented review flow; an admin UI is deferred unless a later review changes scope.

**Data privacy and redaction**

- **FR-031**: Production export to LangSmith or external artifacts MUST be limited to metadata plus approved redacted summaries.
- **FR-032**: Production export MUST NOT include raw resume text, interview answers, job description text, free-form chat, access tokens, refresh tokens, API keys, passwords, or secrets.
- **FR-033**: System MUST classify exported fields as public metadata, internal metadata, sensitive user content, secret, or derived redacted summary.
- **FR-034**: System MUST apply environment-specific export policy for local, CI, staging, and production; staging may send masked prompt/output only for synthetic, golden, or approved staging test data, while other staging traces export metadata plus redacted summaries only.
- **FR-035**: System MUST produce redaction audit evidence before production trace export can be enabled.
- **FR-035a**: Production trace metadata and redacted summaries MUST be retained for 30 days, after which they are deleted or made inaccessible according to the approved retention process.
- **FR-036**: Redaction failure MUST prevent external export while allowing product runtime to continue.

**Version and metric data contract**

- **FR-037**: AI calls, eval runs, product funnel events, dashboard snapshots, feedback, and badcases MUST share stable join fields: run_id, trace_id when present, user hash when allowed, session or thread hash when allowed, graph, node, environment, and version context.
- **FR-038**: Missing required version fields MUST be represented as explicit unknown values and counted in data-quality metrics.
- **FR-039**: PM metrics MUST have documented numerator, denominator, dimensions, source of truth, freshness target, and owner.
- **FR-040**: Dashboard and reports MUST label verified facts, sampled observations, and inferred risks distinctly.

### Key Entities

- **GoldenCase**: Version-controlled eval case for a graph/node; key attributes include case_id, graph, node, input fixture classification, expected output or rubric, schema_version, status, source, upload policy, and reviewer approval when needed.
- **EvalRun**: One eval execution; key attributes include run_id, source revision, branch, environment, started_at, completed_at, aggregate verdicts, per-case results, model, prompt version or fingerprint, rubric version, and artifact links.
- **LangSmithExperimentRef**: External experiment reference; key attributes include run_id, project, dataset, experiment name, URL or external id, sync status, sync error, and synced_at.
- **TraceRunRef**: Join record for debugging; key attributes include trace_id, run_id, graph, node, environment, sampling decision, privacy class, redaction status, and local or external trace link.
- **PMMetricSnapshot**: Dashboard-ready metric row; key attributes include metric_id, period, grain, dimensions, value, numerator, denominator, freshness timestamp, source of truth, and data-quality flags.
- **ProductFunnelEvent**: Product event used for funnel and usage metrics; key attributes include event_name, occurred_at, actor/user/session hash when allowed, feature area, environment, version context, and privacy class.
- **AIInvocationRecord**: Summary of one AI call or logical AI task; key attributes include model, graph, node, prompt fingerprint, rubric version, token counts, estimated cost, latency, retry count, cache fields when available, status, and error category.
- **ResumeDiagnosisOutcome**: Resume-specific outcome summary; key attributes include diagnosis id, status, report viewed flag, suggestions shown, suggestions accepted, score before/after when available, and version context.
- **InterviewOutcome**: Mock-interview summary; key attributes include session id hash, started_at, completed_at, question count, report viewed flag, retry count, status, and failure category.
- **FeedbackSignal**: User or reviewer feedback; key attributes include signal type, helpfulness score or thumbs direction, text feedback presence flag, source, linked run/trace/badcase, and privacy class.
- **Badcase**: Human-reviewable quality issue; key attributes include badcase_id, type, severity, status, reviewer, source, run_id or trace_id, evidence links, privacy class, redaction status, closure reason, and closure timestamp.
- **VersionContext**: Shared attribution fields; key attributes include app_version, release_stage, environment, prompt version or fingerprint, rubric version, model, experiment id/group, graph, node, and schema_version.
- **RedactionPolicy**: Environment-specific export policy; key attributes include environment, allowed field classes, forbidden field classes, summary rules, sampling policy reference, retention policy reference, and policy version; production trace metadata/redacted-summary retention is 30 days.
- **RedactionAudit**: Evidence that export policy was applied; key attributes include audit id, environment, sampled records, forbidden-content checks, failures, reviewer, result, and evidence link.

### Event Schema Draft

All event records should be append-only facts or derived summaries with stable definitions.

| Field | Required | Description |
|---|---:|---|
| `event_name` | yes | Stable event name from the approved event catalog. |
| `occurred_at` | yes | Event time in UTC or an explicitly documented canonical timezone. |
| `environment` | yes | `local`, `ci`, `staging`, or `production`. |
| `release_stage` | yes | Development, release candidate, production, or equivalent stage. |
| `app_version` | yes | Product version or explicit `unknown`. |
| `actor_hash` | conditional | Hash for the actor when permitted by environment policy. |
| `user_hash` | conditional | Hash for the user when permitted by environment policy. |
| `session_hash` | conditional | Hash for browser session, interview session, or equivalent when permitted. |
| `thread_hash` | conditional | Hash for AI thread/session when permitted. |
| `feature_area` | yes | Product area such as resume, interview, feedback, eval, or badcase. |
| `graph` | conditional | Agent graph for AI/eval events. |
| `node` | conditional | Agent node for AI/eval events. |
| `run_id` | conditional | Eval/report run join id when applicable. |
| `trace_id` | conditional | Trace join id when available and permitted. |
| `case_id` | conditional | Golden case id when applicable. |
| `prompt_fingerprint` | conditional | Prompt identity for AI/eval events, or explicit `unknown`. |
| `rubric_version` | conditional | Rubric identity for scored events, or explicit `unknown`. |
| `experiment_id` | conditional | Experiment id/group when the event belongs to an experiment. |
| `privacy_class` | yes | Public metadata, internal metadata, sensitive content, secret, or redacted summary. |
| `redaction_status` | yes | Not required, pending, passed, failed, or not exportable. |
| `metadata` | yes | Structured metadata limited by the environment policy. |

### Event Catalog Draft

| Event | Purpose | Primary PM Metrics |
|---|---|---|
| `product.visit` | Product entry signal | UV, visit-to-register/login conversion |
| `auth.registered` | New account created | Registered users, funnel conversion |
| `auth.logged_in` | Returning user entry | Active users, funnel conversion |
| `resume.created_or_uploaded` | Resume journey started | Resume funnel entry |
| `resume.diagnosis_requested` | Resume AI task started | Diagnosis demand |
| `resume.diagnosis_completed` | Diagnosis success/failure | Diagnosis success rate, latency |
| `resume.report_viewed` | User consumed diagnosis report | Report view rate |
| `resume.suggestion_shown` | Suggestion made visible | Suggestions shown |
| `resume.suggestion_accepted` | User accepted suggestion | Suggestion acceptance rate |
| `interview.started` | Mock interview started | Interview starts |
| `interview.completed` | Mock interview completed | Completion rate, question count |
| `interview.report_viewed` | User consumed interview report | Interview report view rate |
| `ai.call_completed` | AI call succeeded | AI success, token/cost, latency |
| `ai.call_failed` | AI call failed | Failure rate, retry analysis |
| `feedback.submitted` | User feedback captured | Feedback volume, sentiment/helpfulness |
| `badcase.created` | Review item opened | Open badcases |
| `badcase.classified` | Review item triaged | Type/severity distribution |
| `badcase.closed` | Review item resolved | Closure rate, fix result |
| `eval.run_started` | Eval run began | Eval volume/freshness |
| `eval.run_completed` | Eval run completed | Pass rate, failures, trend |
| `eval.experiment_synced` | LangSmith sync completed/failed | Experiment availability |

### Metric Schema Draft

| Field | Required | Description |
|---|---:|---|
| `metric_id` | yes | Stable metric key used in dashboard and reports. |
| `display_name` | yes | PM-facing label. |
| `grain` | yes | Time grain such as day, week, release, or eval run. |
| `period_start` / `period_end` | yes | Metric window. |
| `dimensions` | yes | Environment, version, model, graph, node, experiment, and other approved segments. |
| `numerator` | conditional | Count or value numerator where applicable. |
| `denominator` | conditional | Denominator where applicable. |
| `value` | yes | Final computed value. |
| `unit` | yes | Count, percent, currency, tokens, milliseconds, score, or days. |
| `source_of_truth` | yes | Canonical internal source or artifact type. |
| `freshness_at` | yes | Last update time for this metric. |
| `quality_flags` | yes | Missing version fields, delayed ingestion, sampled data, or partial data. |

### PM Dashboard V1 Pages And Metrics

| Page / Panel | Required Metrics | Required Filters |
|---|---|---|
| Product Overview | UV, registered users, active users, completed AI tasks, AI success rate, total tokens, estimated cost, open badcases | date range, environment, release stage, app version |
| Core Funnel | visit/login/register, resume created/uploaded, diagnosis success, report view, suggestion accept, interview complete, feedback view, per-step conversion, largest drop-off | date range, environment, release stage, app version, experiment group |
| Resume Diagnosis | diagnosis count, success/failure rate, report views, suggestions shown, suggestions accepted, acceptance rate, score delta | date range, app version, prompt fingerprint, rubric version, model |
| Mock Interview | starts, completions, completion rate, average question count, report views, retries, failure category | date range, app version, prompt fingerprint, rubric version, model |
| AI Operations | call count, token usage, estimated cost, p50/p95 latency, success/failure, retry count, model, graph, node, prompt fingerprint | date range, environment, graph, node, model, prompt fingerprint |
| Feedback And Badcase | thumbs up/down or equivalent, helpfulness score, text feedback count, badcase type/status/severity/source/fix result, closure rate | date range, source, type, status, severity, reviewer |
| Version And Experiment | app version, release stage, prompt fingerprint, rubric version, model, experiment id/group, run_id, trace coverage | date range, environment, release stage, version fields |

### LangSmith Integration Boundary

- LangSmith is the MVP workbench for datasets, eval experiments, trace drill-down, and feedback-style inspection.
- LangSmith is not the canonical product analytics store, cost ledger, quota ledger, compliance record, or only copy of eval evidence.
- Local JSON reports, CI artifacts, InterCraft-controlled metrics, and evidence files remain readable without LangSmith access.
- Local and CI LangSmith usage is allowed for synthetic or approved golden data.
- Staging may send masked prompt/output only for synthetic, golden, or approved staging test data; other staging traces are limited to metadata plus redacted summaries.
- Production trace export is deferred until redaction, sampling, retention, and human review evidence are complete.
- Golden-case upload must respect case-level privacy classification and schema versioning.
- Experiments must be joinable by run_id, git/source revision, branch, case_id, graph, node, prompt fingerprint, rubric version, and model.
- LangSmith failures must be reported as sync failures, not as product runtime failures.

### Badcase Human Review Boundary

- The user is the initial badcase reviewer and approval owner for MVP.
- Human review is required for badcase classification changes that affect severity, closure, golden-case promotion, baseline refresh, emergency override, and production trace promotion.
- Baseline refresh and emergency override require dual approval from the PM business owner and technical owner.
- Automation may suggest classification, duplicate links, affected version fields, and likely failure category, but human classification is authoritative.
- A badcase can be closed only with a resolution category: fixed, duplicate, cannot reproduce, expected behavior, privacy issue resolved, deferred, or rejected.
- A badcase promoted to a golden case must include redaction status, reviewer approval, source metadata, and a reason the case should protect future behavior.
- First-month golden-case promotion uses a CLI/documented review flow; admin UI is deferred.
- Dashboard badcase metrics are operational summaries and do not replace the review record.

### Data Redaction And Privacy Boundary

- Production export policy is fixed for MVP: metadata plus redacted summaries only.
- Production trace metadata and redacted summaries are retained for 30 days.
- Forbidden production export content includes raw resumes, interview answers, job descriptions, free-form user text, secrets, access tokens, refresh tokens, passwords, and API keys.
- Public metadata may include graph, node, model, duration, token counts, status, environment, release stage, and version fields.
- Internal metadata may include hashed user, session, thread, run, trace, and prompt identifiers when policy permits.
- Derived summaries may be exported only when generated through an approved redaction path and marked as redacted summary.
- Redaction policy must be environment-specific and versioned.
- Staging export policy is fixed for MVP: masked prompt/output is allowed only for synthetic, golden, or approved staging test data; other staging traces use metadata plus redacted summaries only.
- Redaction audit evidence must include happy-path and failure-path samples before production trace export is enabled.
- Runtime must fail open when export fails: user-facing product behavior continues while export/reporting failure is recorded.

### CI / Nightly / Staging Eval Flow

- **PR flow**: prompt-adjacent changes run deterministic golden-case eval; failures block merge unless a documented human override is recorded.
- **PR artifacts**: every eval run produces a local report with run_id, source revision, branch, graph, node, case_id, schema_version, prompt fingerprint, rubric version, model, aggregate verdicts, and failure details.
- **LangSmith PR sync**: when enabled, PR eval results sync to a LangSmith experiment using the same run_id; sync failure does not rewrite local verdicts.
- **Nightly flow**: real-model eval can run on schedule or manually as report-only within the approved medium budget of about 5M tokens or $50 per night and $1000 per month until baseline approval rules are decided.
- **Nightly artifacts**: reports include pass rate, known regression recall, stale cases, cost estimate, latency trend, retry/failure trend, and budget status.
- **Staging flow**: staging traces and eval reports can be collected using the approved staging policy; masked prompt/output is limited to synthetic, golden, or approved staging test data, and staging is non-blocking by default.
- **Release-candidate flow**: staging eval can become a release gate only after gate criteria, owner, dual-approval override process, and payload policy are documented.
- **Production flow**: production trace export remains off for MVP until redaction, sampling, 30-day retention, and human review evidence are accepted.

## Success Criteria

### Measurable Outcomes

- **SC-001**: PM can answer the six Dashboard V1 questions from ADR-002 within one dashboard session and without opening developer-only tools.
- **SC-002**: 100% of Dashboard V1 metrics have documented numerator, denominator where applicable, dimensions, source of truth, freshness target, and owner.
- **SC-003**: Core funnel panels show counts and conversion rates for every required step with explicit zero or missing-data states.
- **SC-004**: Resume diagnosis and mock interview panels each expose adoption, completion, and outcome metrics segmented by at least app version, prompt fingerprint, rubric version, and model.
- **SC-005**: 100% of prompt-adjacent PR eval failures include run_id, case_id, graph, node, prompt fingerprint, rubric version, failure reason, and local artifact reference.
- **SC-006**: With LangSmith enabled, local eval reports and LangSmith experiments share the same run_id and source revision for 100% of synced runs.
- **SC-007**: LangSmith sync failures do not change local eval pass/fail outcomes in 100% of runs.
- **SC-008**: Production export privacy audit finds zero raw resumes, interview answers, job descriptions, free-form user text, or secrets in exported production payload samples before production export is enabled.
- **SC-009**: 100% of badcases closed in MVP include reviewer, classification, closure reason, fix result or rejection reason, and evidence or rationale.
- **SC-010**: 100% of eval runs, AI invocation summaries, dashboard metric snapshots, and badcases include required version fields or explicit `unknown` values.
- **SC-011**: Nightly real-model eval remains report-only, respects the approved medium budget of about 5M tokens or $50 per night and $1000 per month, and cannot refresh baselines unless both the PM business owner and technical owner approve the refresh.
- **SC-013**: 100% of emergency overrides and baseline refreshes record dual approval from the PM business owner and technical owner, with reason, evidence, timestamp, and affected gate or baseline.
- **SC-014**: 100% of production trace metadata and redacted-summary records are deleted or made inaccessible after the 30-day retention window.
- **SC-015**: 100% of first-month badcase-to-golden-case promotions can be completed through the documented CLI/review flow without requiring an admin UI.
- **SC-012**: PM dashboard and generated reports label verified facts, sampled observations, and inferred risks distinctly in every report section that mixes those evidence types.

## Assumptions

- The dashboard audience for V1 is internal PM users, not end users, executives, finance, or developer-only debugging users.
- Existing authentication and internal access controls will protect PM Dashboard V1; detailed permission design belongs in planning.
- Existing local eval work from feature 026 and trace work from feature 029 are the starting points for eval and trace identifiers.
- Product analytics and AI cost metrics are sourced from InterCraft-controlled data or generated artifacts; LangSmith links are supplementary.
- CI and local eval can use synthetic or version-controlled golden data without production raw content.
- Golden-case labels and rubrics require human review before they become baseline-protecting evidence.
- Dashboard V1 may start with batch or report-style freshness as long as freshness is explicit; true real-time analytics is not required for MVP.
- Cost metrics are estimates unless reconciled with an approved billing source; Dashboard V1 must label them as estimates.
- The current source layout remains `src/` for frontend and `backend/app/` for backend when later implementation planning begins.

## Risks And Boundary Conditions

- Small golden datasets can overfit and make eval pass rates look healthier than product reality.
- PM metrics can overclaim certainty if sampled traces, inferred badcase categories, and verified product facts are not labeled separately.
- LangSmith Cloud introduces vendor availability, permission, pricing, and data-governance risks; local artifacts must remain canonical.
- Privacy failures are high impact because resume, interview, JD, and free-form career content can contain sensitive personal data.
- Version fields can drift or be missing in older records; dashboards must track unknown rates instead of hiding them.
- Nightly real-model eval can remain noisy even with the medium budget cap; it must stay report-only unless baseline refreshes receive dual approval.
- Badcase closure quality depends on human review discipline; automation can organize but not replace reviewer judgment.
- Deferring the badcase promotion admin UI reduces MVP scope but may create manual overhead if first-month badcase volume is high.
- Staging payload policy trades debug fidelity for privacy; masked prompt/output must remain limited to synthetic, golden, or approved staging test data.
- Production trace retention is fixed at 30 days, which improves debugging and trend review but increases the privacy exposure window compared with shorter retention.
- Baseline refresh and emergency override authority is fixed for MVP as dual approval by the PM business owner and technical owner.

## Clarifications / Open Questions

All previously open MVP questions were resolved in the 2026-06-26 clarification session. Future planning may add new questions if implementation evidence exposes new ambiguity.
