# Feature Specification: Production-Grade LLM Evals

**Feature Branch**: `[046-production-llm-evals]`

**Created**: 2026-07-05

**Status**: Draft

**Input**: User description: "整理一个REQ，将现有的LLM Evals体系提升到生产级别"

## Current Baseline And Production Gap

REQ-045 completed the foundation for an OTel-first, LangSmith-assisted LLM Ops
eval workflow. The system can run local golden evals, correlate trace/run
identity, enforce destination export policy, sync an eval report to LangSmith
as a run-level trace, compare experiments locally, run report-only judge
verdicts, promote badcases into candidate eval cases, and create prompt
improvement proposals.

The remaining gap is the difference between a working foundation and a
production-grade eval operating system:

- LangSmith sync currently proves run-level trace upload, but not a complete
  Dataset + Experiment + Evaluation Results workflow with stable deep links.
- Eval reports can contain LangSmith metadata, but production operators still
  need clickable URLs, screenshots, and repeatable evidence that the LangSmith
  workbench matches local run ids and case ids.
- Local eval gates exist, but production release readiness needs clear
  prompt-adjacent merge gates, nightly coverage, release-candidate evidence,
  and full-suite blockers resolved or explicitly waived.
- Judge feedback exists in report-only form, but production use requires a
  calibration lifecycle, drift review, disagreement handling, and a clear
  threshold before judge results can block a release.
- Export policy exists, but production operations need routine audit evidence,
  retention/access review, secret-leak prevention, and full-content LangSmith
  export proof.
- Current evidence is mostly local command output and screenshots. Production
  operators need a documented workflow that joins local reports, trace views,
  LangSmith pages, release decisions, and incident follow-up in one auditable
  chain.

Desired end state: InterCraft has a production LLM Evals operating system where
local artifacts remain canonical, OpenTelemetry-compatible correlation remains
the company-wide observability standard, and LangSmith provides a verified AI
quality workbench for datasets, experiments, feedback, and debugging. A prompt,
model, rubric, or agent change cannot reach production without visible eval
evidence, governed export decisions, and human-owned release accountability.

## Scope Boundary

Included:

- Real LangSmith dataset, experiment, run, feedback, and deep-link evidence
- Production eval gates for prompt-adjacent changes and release candidates
- Nightly and release-candidate eval operating workflow
- Judge calibration, drift review, and report-only-to-blocking promotion rules
- Expanded eval coverage across high-risk AI surfaces
- Production export governance, retention, access, and secret-leak audit
- Operator/admin evidence workflow for PMs, AI engineers, and on-call owners
- Runbooks, screenshots, and acceptance evidence for production operation

Excluded:

- Automatic prompt deployment
- Automatic golden baseline refresh without human approval
- Replacing local eval artifacts with LangSmith as the sole source of truth
- General admin console redesign unrelated to LLM Evals operations
- Unrelated agent runtime refactors or checkpointer changes

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Verify Real LangSmith Experiment Sync (Priority: P1)

As an AI engineer, I want every sync-enabled eval run to create or update real
LangSmith dataset, experiment, run, and feedback records with stable deep links
so that I can debug eval results in LangSmith and prove the workbench matches
the local canonical report.

**Why this priority**: This is the main gap discovered after REQ-045. Run-level
trace upload works, but production-grade assisted evaluation requires verified
LangSmith dataset and experiment evidence, not only a trace row.

**Independent Test**: Run a sync-enabled eval with valid credentials, then
verify that the local report contains non-empty LangSmith dataset, experiment,
run, and feedback references; the referenced LangSmith pages show matching run
ids, case ids, source revision, dataset version, and verdict summary.

**Acceptance Scenarios**:

1. **Given** a configured LangSmith workspace and a local eval report, **When**
   an operator syncs the report, **Then** LangSmith contains a dataset,
   experiment, and one or more run records that match the local run id and case
   ids.
2. **Given** sync completes successfully, **When** the operator opens the local
   eval report or operation guide, **Then** it contains clickable LangSmith
   links for the dataset, experiment, and relevant run details.
3. **Given** a LangSmith sync succeeds but a deep link cannot be resolved,
   **When** the sync result is recorded, **Then** the run is marked incomplete
   for production evidence and the missing link is visible to the operator.
4. **Given** LangSmith is unavailable, **When** a production eval gate runs,
   **Then** the local verdict remains canonical and the missing LangSmith
   evidence is classified as an integration readiness issue rather than a
   hidden success.

---

### User Story 2 - Enforce Production Eval Gates Before Release (Priority: P1)

As a release owner, I want prompt-adjacent and release-candidate changes to pass
the right eval gates before production promotion so that quality regressions are
caught before users see them.

**Why this priority**: A production eval system must influence release
decisions. Without clear gates, evals remain advisory even if they produce good
reports.

**Independent Test**: Submit representative prompt, rubric, model, dataset, and
agent behavior changes through the release workflow and verify that required
eval gates run, block known regressions, preserve evidence, and allow
non-adjacent changes to avoid unnecessary expensive evals.

**Acceptance Scenarios**:

1. **Given** a prompt, rubric, model, dataset, or agent behavior change, **When**
   it enters the merge path, **Then** the required eval gate runs and attaches
   a release evidence record.
2. **Given** a known golden regression is detected, **When** the gate completes,
   **Then** the change is blocked with failure reasons, affected cases, trace
   references, and owner-visible next actions.
3. **Given** a release-candidate promotion is requested, **When** the release
   owner reviews readiness, **Then** the latest passing eval report, LangSmith
   evidence, export audit, judge status, and coverage summary are visible in one
   release decision record.
4. **Given** the full test suite has unrelated legacy blockers, **When** a
   release decision is made, **Then** the blockers are either resolved or
   explicitly waived with owner, reason, expiration, and residual risk.

---

### User Story 3 - Operate Evals With Production SLOs And Alerts (Priority: P1)

As an on-call owner, I want the LLM Evals workflow itself to have health
signals, service-level objectives, and alerts so that silent eval failures,
coverage drops, or sync problems do not erode release confidence.

**Why this priority**: Production-grade evals are an operational system. If the
eval infrastructure fails silently, teams may ship without meaningful quality
coverage.

**Independent Test**: Simulate eval failure, LangSmith sync failure, coverage
drop, judge calibration drift, and export policy rejection; verify that each
condition creates an operator-visible signal with severity, owner, and
recommended action.

**Acceptance Scenarios**:

1. **Given** nightly evals fail or do not run, **When** the expected reporting
   window passes, **Then** an operator-visible alert identifies the missing or
   failed run and its owner.
2. **Given** LangSmith sync success rate drops below the accepted threshold,
   **When** operators inspect eval health, **Then** they can see affected runs,
   failure reasons, and whether local verdicts remain available.
3. **Given** eval coverage drops for a high-risk AI surface, **When** the
   coverage summary is generated, **Then** the affected surface is marked
   below production readiness and linked to required follow-up.
4. **Given** eval infrastructure fails during an end-user workflow, **When** the
   workflow completes or fails, **Then** user-facing AI behavior is not blocked
   solely by observability or eval export failures.

---

### User Story 4 - Govern Production Full-Content Export (Priority: P1)

As a product and data owner, I want production full-content LangSmith export to
remain explicit, auditable, and access-controlled so that AI debugging can use
real payloads without leaking secrets or bypassing retention rules.

**Why this priority**: The user has explicitly allowed complete unredacted AI
payloads to LangSmith in production. That permission is powerful and must be
operationalized with evidence, scope, retention, and secret protection.

**Independent Test**: Run export audits over payloads containing resumes, job
descriptions, interview text, LLM inputs, LLM outputs, user identifiers, and
secret-like values; verify that approved LangSmith full-content export is
allowed while operational secrets are blocked and all decisions are recorded.

**Acceptance Scenarios**:

1. **Given** a production LangSmith export includes full AI payloads, **When**
   the export completes, **Then** the evidence record includes destination,
   environment, owner, access scope, retention, policy version, representation
   level, and decision id.
2. **Given** a payload includes application secrets, credentials, access
   tokens, or infrastructure passwords, **When** export is attempted, **Then**
   the export is blocked even if full-content LangSmith export is otherwise
   enabled.
3. **Given** a retention or access-scope review is due, **When** the operator
   audits exported eval artifacts, **Then** expired, over-retained, or
   over-broadly shared records are visible and actionable.
4. **Given** a non-LangSmith destination requests full payloads, **When** export
   policy is evaluated, **Then** raw AI payloads are redacted, summarized, or
   blocked according to the destination policy.

---

### User Story 5 - Expand High-Risk Eval Coverage (Priority: P2)

As a quality owner, I want eval coverage across all high-risk AI surfaces so
that production readiness is not based on one narrow interview slice.

**Why this priority**: REQ-045 validated the workflow using a focused case set.
Production-grade quality requires breadth: critical agents, tool use,
multi-turn behavior, structured output, policy safety, and production badcases.

**Independent Test**: Inspect the coverage inventory and run the production
eval suite; verify that each high-risk AI surface has golden, candidate, and
report-only coverage where appropriate, including production-sourced badcases.

**Acceptance Scenarios**:

1. **Given** the coverage inventory is generated, **When** a high-risk AI
   surface is missing required coverage, **Then** the surface is marked not
   production-ready with a clear owner and remediation path.
2. **Given** a production badcase is promoted, **When** it enters the eval
   dataset lifecycle, **Then** it starts as candidate or report-only and cannot
   block merges until human acceptance.
3. **Given** a case is deprecated, rejected, or replaced, **When** reports are
   generated, **Then** the lifecycle decision and replacement relationship are
   visible.
4. **Given** a high-risk surface changes behavior, **When** production evals run,
   **Then** the relevant golden and candidate cases are included in the
   readiness summary.

---

### User Story 6 - Promote Judge Feedback To Production Safely (Priority: P2)

As a PM or AI quality reviewer, I want LLM-as-Judge feedback to move from
report-only to release-impacting only after calibration and ongoing review so
that subjective quality signals help decisions without becoming arbitrary.

**Why this priority**: Judge feedback is valuable but risky. Production use
requires calibration, human disagreement review, drift detection, and a clear
promotion path.

**Independent Test**: Calibrate a judge rubric with human labels, compare it
against held-out cases, review disagreements, and verify that only calibrated
rubrics can affect release decisions.

**Acceptance Scenarios**:

1. **Given** a judge rubric has insufficient human labels or agreement, **When**
   evals run, **Then** judge feedback is marked report-only and cannot block a
   merge by itself.
2. **Given** a rubric meets calibration thresholds, **When** it is promoted,
   **Then** the promotion record includes owner, label count, agreement rate,
   scope, review date, and rollback conditions.
3. **Given** judge disagreement or drift exceeds the accepted threshold, **When**
   the drift review runs, **Then** the rubric is downgraded, suspended, or sent
   for human review before it can block releases.
4. **Given** a judge verdict affects a release decision, **When** the decision
   is audited, **Then** reviewers can inspect score, rationale summary,
   calibration evidence, and disagreement context.

---

### User Story 7 - Give Operators A Single Production Evidence View (Priority: P3)

As a PM, release owner, or on-call engineer, I want a single evidence view that
summarizes eval health, release readiness, LangSmith links, export policy,
coverage, and open action items so that production decisions are made from one
shared source.

**Why this priority**: After the production workflow is reliable, the next
usability gap is operational ergonomics. Teams should not stitch together local
command output, screenshots, trace pages, and spreadsheets by hand.

**Independent Test**: Open the production evidence view for a recent run and
verify that an operator can answer whether the release is safe, what failed,
where to debug, and who owns follow-up within five minutes.

**Acceptance Scenarios**:

1. **Given** a production or release-candidate eval run exists, **When** an
   operator opens the evidence view, **Then** it shows status, gate result,
   LangSmith links, trace links, export policy decision, judge status, coverage
   summary, and owner.
2. **Given** a run has failures, **When** the operator filters to failed cases,
   **Then** each case shows failure reason, impacted surface, artifact, trace,
   LangSmith reference when available, and suggested next action.
3. **Given** a run is blocked by missing evidence rather than quality failure,
   **When** the operator reviews it, **Then** the missing evidence is clearly
   distinguished from model or prompt regression.

### Edge Cases

- LangSmith credentials are valid locally but invalid in CI or production.
- LangSmith upload succeeds but dataset, experiment, feedback, or web URL
  creation only partially succeeds.
- LangSmith UI or API changes produce different link shapes or delayed page
  availability.
- A local eval passes but LangSmith sync is delayed, rate-limited, or missing
  feedback records.
- A release candidate has passing evals but stale dataset versions.
- A prompt change improves one AI surface while regressing another.
- A production badcase contains user-deleted, expired, or policy-restricted
  content.
- Export policy allows full-content LangSmith payloads but secret detection
  finds credential-like values.
- Judge feedback conflicts with deterministic checks or human labels.
- Nightly evals exhaust cost or token budget before completing.
- Full-suite blockers are unrelated to LLM Evals but still affect release
  confidence.
- Trace retention expires before a linked eval is audited.
- Two experiments use the same display name but different source revisions.
- An operator lacks access to the LangSmith workspace referenced by evidence.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST distinguish run-level LangSmith trace sync from
  production LangSmith dataset and experiment sync in all reports and evidence.
- **FR-002**: System MUST create or update real LangSmith dataset references for
  sync-enabled eval suites and record the local dataset version that produced
  them.
- **FR-003**: System MUST create real LangSmith experiment references for
  baseline and candidate eval runs and record experiment identity in the local
  report.
- **FR-004**: System MUST attach eval case outputs, verdicts, and feedback
  records to the corresponding LangSmith run or experiment record.
- **FR-005**: System MUST write stable, clickable LangSmith URLs for dataset,
  experiment, run, and feedback evidence when those pages are available.
- **FR-006**: System MUST mark production evidence incomplete when LangSmith sync
  reports success but required dataset, experiment, run, feedback, or URL
  references are unavailable.
- **FR-007**: System MUST preserve local eval artifacts as the canonical source
  of release verdicts even when LangSmith evidence exists.
- **FR-008**: System MUST allow a sync-enabled run to be replayed or reconciled
  without duplicating production evidence.
- **FR-009**: System MUST require prompt, rubric, model, dataset, and agent
  behavior changes to produce a release evidence record before production
  promotion.
- **FR-010**: System MUST block production promotion when required golden evals
  fail unless a dual-owner waiver is recorded with reason, expiry, and residual
  risk.
- **FR-011**: System MUST identify non-prompt-adjacent changes that do not
  require expensive LLM eval gates while still preserving release auditability.
- **FR-012**: System MUST include source revision, branch or release candidate,
  dataset version, prompt fingerprint, rubric version, model version, owner, and
  gate result in release evidence.
- **FR-013**: System MUST record whether full-suite blockers are resolved,
  accepted with waiver, or unrelated to the LLM Evals release decision.
- **FR-014**: System MUST define production health states for LLM Evals, including
  healthy, degraded, integration incomplete, coverage insufficient, and blocked.
- **FR-015**: System MUST alert or surface an operator-visible action item when
  scheduled evals fail, do not run, or miss their reporting window.
- **FR-016**: System MUST track LangSmith sync success rate, sync latency,
  missing-link rate, export policy failure rate, eval pass rate, coverage level,
  and judge calibration state.
- **FR-017**: System MUST show whether eval infrastructure failures affect local
  release verdicts, external evidence only, or end-user AI workflows.
- **FR-018**: System MUST fail open for end-user AI workflows when eval,
  observability, or external export infrastructure is unavailable.
- **FR-019**: System MUST require export policy decisions for every production
  LangSmith full-content export.
- **FR-020**: System MUST record destination, environment, owner, access scope,
  retention period, representation level, policy version, decision id, and
  decision time for production exports.
- **FR-021**: System MUST block export of application secrets, credentials,
  access tokens, and infrastructure passwords regardless of destination policy.
- **FR-022**: System MUST allow raw resumes, job descriptions, interview text,
  LLM inputs, and LLM outputs to reach LangSmith only under an approved
  production full-content policy.
- **FR-023**: System MUST downgrade, redact, summarize, or block raw AI payloads
  for destinations that are not approved for full-content LangSmith export.
- **FR-024**: System MUST support retention and access-scope audits for exported
  eval and trace evidence.
- **FR-025**: System MUST maintain an inventory of high-risk AI surfaces and the
  minimum eval coverage required for each surface.
- **FR-026**: System MUST mark a high-risk AI surface below production readiness
  when required golden, candidate, or report-only coverage is missing.
- **FR-027**: System MUST support production-sourced badcase promotion into
  candidate eval cases with source trace, source artifact, redaction audit,
  owner, approval state, and lifecycle status.
- **FR-028**: System MUST prevent candidate and report-only cases from blocking
  merges until they are explicitly accepted as golden cases.
- **FR-029**: System MUST preserve deprecated, rejected, and replaced eval case
  lifecycle decisions in reports and coverage summaries.
- **FR-030**: System MUST require judge rubrics to remain report-only until
  calibration thresholds or an explicit owner waiver are recorded.
- **FR-031**: System MUST record judge rubric owner, label count, agreement rate,
  review date, scope, model identity, rollback conditions, and status.
- **FR-032**: System MUST surface judge disagreements with deterministic checks
  or human labels for review.
- **FR-033**: System MUST downgrade or suspend release-impacting judge rubrics
  when drift or disagreement exceeds accepted thresholds.
- **FR-034**: System MUST provide an operator evidence view that joins local eval
  reports, trace references, LangSmith references, export policy decisions,
  judge state, coverage state, and release decision status.
- **FR-035**: System MUST distinguish quality failures from missing evidence,
  integration failures, coverage gaps, and policy blocks in operator-facing
  reports.
- **FR-036**: System MUST provide a repeatable operation guide with screenshots
  for successful local eval, successful LangSmith experiment evidence, export
  policy audit, judge calibration, experiment comparison, badcase promotion, and
  release readiness review.
- **FR-037**: System MUST record human approvals for golden case promotion,
  judge promotion, waivers, prompt/rubric proposal approval, and production
  release decisions.
- **FR-038**: System MUST ensure prompt and rubric improvement proposals remain
  proposals until comparison evidence and human approval are recorded.
- **FR-039**: System MUST support production incident follow-up from failed eval
  or badcase evidence to owner, action item, target dataset, and verification
  run.
- **FR-040**: System MUST provide requirement-level completion evidence before
  this feature is marked done, including local reports, LangSmith screenshots,
  export audit output, coverage summary, health signal proof, and release
  readiness proof.

### Key Entities *(include if feature involves data)*

- **ProductionEvalRun**: A production, nightly, or release-candidate eval
  execution with status, source revision, dataset version, coverage summary,
  gate result, owner, and evidence completeness state.
- **LangSmithDatasetRef**: A verified LangSmith dataset reference linked to a
  local dataset version, suite, owner, and access scope.
- **LangSmithExperimentRef**: A verified LangSmith experiment reference linked
  to local eval run ids, baseline/candidate context, source revision, and
  clickable evidence URLs.
- **LangSmithRunEvidence**: A synced run, feedback, or trace record that can be
  matched to local case ids, trace ids, run ids, verdicts, and artifacts.
- **ReleaseEvidenceRecord**: The decision package for a prompt-adjacent change
  or release candidate, including eval status, LangSmith evidence, export
  policy, judge state, coverage, waivers, and owner decision.
- **EvalHealthSignal**: A production health indicator for eval infrastructure,
  sync reliability, coverage, policy, calibration, and scheduled run freshness.
- **EvalCoverageInventory**: The list of high-risk AI surfaces, required
  coverage levels, current case counts, lifecycle mix, and readiness status.
- **JudgeCalibrationRecord**: The human-label and agreement evidence that
  determines whether a judge rubric is report-only, release-impacting,
  suspended, or retired.
- **ExportGovernanceRecord**: The destination policy decision and audit metadata
  attached to any external trace or eval export.
- **BadcaseDatasetPromotion**: A production or staging issue promoted into a
  candidate eval case with redaction, ownership, approval, and source evidence.
- **OperatorEvidenceView**: The human-facing summary that joins eval, trace,
  LangSmith, export, coverage, judge, and release readiness information.
- **EvalActionItem**: A follow-up task created from missing evidence, failed
  evals, policy blocks, coverage gaps, judge drift, or badcase promotion needs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of sync-enabled production or release-candidate eval runs
  produce local artifacts plus verified LangSmith dataset, experiment, and run
  references, or are explicitly marked integration incomplete.
- **SC-002**: At least 95% of successful sync-enabled eval runs appear in
  LangSmith with matching local run id, case id, dataset version, and source
  revision within 2 minutes.
- **SC-003**: 100% of successful production LangSmith sync records include at
  least one clickable LangSmith URL that operators can open without manually
  searching by run name.
- **SC-004**: Known golden regressions block prompt-adjacent production
  promotion with a non-zero gate result and an actionable failure report.
- **SC-005**: 100% of release-candidate decisions include local eval evidence,
  LangSmith evidence status, export policy status, judge status, coverage
  status, and owner decision.
- **SC-006**: Scheduled production evals report healthy, degraded, blocked, or
  integration-incomplete status within 5 minutes of the expected reporting
  window.
- **SC-007**: For high-risk AI surfaces, at least five surfaces are covered by
  production-ready eval inventory before this feature is marked done:
  interview scoring/reporting, error coaching, resume optimization, ability
  diagnosis, and general coaching.
- **SC-008**: 100% of production full-content LangSmith exports include
  destination, environment, owner, access scope, retention, representation
  level, policy version, decision id, and decision time.
- **SC-009**: Seeded secret-like values are blocked from external export in
  100% of export governance acceptance cases.
- **SC-010**: Judge rubrics affect release decisions only after at least 30
  human-labeled examples and at least 80% agreement on the target decision
  boundary, unless an explicit owner waiver is recorded.
- **SC-011**: A PM or on-call owner can determine release readiness, failure
  cause, LangSmith evidence location, and next owner from the operator evidence
  view within 5 minutes for a recent run.
- **SC-012**: 100% of production-sourced badcase promotions start as candidate
  or report-only cases and include redaction audit and human approval metadata.
- **SC-013**: End-user AI workflows continue or fail for user-facing reasons;
  eval, tracing, or external export outages alone do not block the user
  workflow.
- **SC-014**: Production operation guide includes screenshots for local eval
  success, real LangSmith experiment evidence, export audit, judge calibration,
  experiment comparison, badcase promotion, and release readiness.
- **SC-015**: This feature cannot be marked done while unresolved full-suite
  blockers remain unowned, unwaived, or unexplained in release readiness
  evidence.

## Assumptions

- REQ-045 is the baseline foundation and remains done; this requirement raises
  the operating level rather than replacing it.
- The organization has or will configure a LangSmith workspace, production-safe
  credentials, and appropriate user access for AI operators.
- Production LangSmith export may include complete unredacted AI payloads only
  under an explicit full-content destination policy.
- Application secrets, credentials, access tokens, and infrastructure passwords
  are never allowed in external observability destinations.
- Local eval reports remain the canonical evidence for release verdicts even
  when LangSmith evidence is present.
- OpenTelemetry-compatible trace identity remains the cross-system correlation
  standard; LangSmith is an assisted AI workbench layered on top.
- Existing admin or PM surfaces may host the operator evidence view, but a broad
  admin console redesign is out of scope.
- Automatic prompt deployment and automatic golden baseline refresh remain out
  of scope; human approval is required for release-impacting changes.
- Initial production coverage targets focus on the highest-risk AI surfaces
  rather than every possible prompt path.
- If an external tool changes behavior or link formats, the production evidence
  workflow must detect incomplete evidence rather than silently pass.
