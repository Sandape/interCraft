# Feature Specification: Agent Eval-Driven Self-Improvement Loop

**Feature Branch**: `[026-agent-eval-loop]`

**Created**: 2026-06-24

**Status**: Draft

**Input**: User description: "为 5 个 LangGraph agent (interview / error_coach / resume_optimize / ability_diagnose / general_coach) 建立 eval 驱动的质量护栏和自我进化能力。"

## User Scenarios & Testing

### User Story 1 - Prompt Regression Blocks Bad Merges (Priority: P1)

As a maintainer, when a contributor proposes a change to any prompt-adjacent file (system prompt, tool description, node logic that shapes LLM input), I want an automated eval suite to run before the change can merge, so that prompt regressions — like the past Chinese-fidelity regression where a zh-CN prompt silently produced English output — are caught automatically instead of being discovered in production.

**Why this priority**: This is the core defensive value. The project has shipped 20+ specs with prompt-driven LLM behavior, and the existing 64/64 E2E tests are all deterministic-mock-based. Without this gate, every prompt change is an unmonitored risk to scoring stability, language fidelity, and hallucination rate. P1 because it is the only story that directly prevents production regressions; every other story supports it.

**Independent Test**: Can be fully tested by intentionally reverting a known-good prompt to its pre-fix version (e.g., the prompt that produced English summaries) and observing that the eval gate blocks the merge with a labeled metric regression.

**Acceptance Scenarios**:

1. **Given** a contributor opens a PR touching a prompt-adjacent file, **When** CI runs, **Then** the eval suite executes against the active model and posts a metric report to the PR.
2. **Given** the eval report shows language fidelity dropped below threshold on the interview report node, **When** the maintainer attempts to merge, **Then** the merge is blocked with a message identifying the regressed node and metric.
3. **Given** a maintainer needs to ship an emergency fix and the gate is failing, **When** they invoke the documented override, **Then** the merge proceeds with the override recorded in an audit log.
4. **Given** the eval suite passes, **When** the maintainer refreshes the baseline, **Then** the new baseline is stored with the git SHA and a reviewer signature.

---

### User Story 2 - Golden Dataset Per Node (Priority: P2)

As a quality engineer, for each of the 5 agent graphs (interview / error_coach / resume_optimize / ability_diagnose / general_coach), I want a curated golden dataset of input→expected-output pairs covering each high-value node, so that any prompt change can be replayed against a known-good set of cases before it ships.

**Why this priority**: The golden dataset is the foundation that makes US1 possible. Without curated cases, the eval gate has nothing to compare against. P2 (not P1) because it is a prerequisite that can be built incrementally per graph — a partial dataset still delivers value for the nodes it covers.

**Independent Test**: Can be fully tested by running the eval suite against the current production prompt with the golden dataset and confirming all cases pass with the stored baseline metrics.

**Acceptance Scenarios**:

1. **Given** a developer adds a golden case for the interview score node, **When** they commit it, **Then** the case is version-controlled alongside the source and picked up by the next eval run.
2. **Given** a golden case is run through the eval suite, **When** the active model produces output, **Then** the case records input, expected, actual, and per-metric verdict.
3. **Given** a golden case becomes stale due to a state schema change, **When** the eval suite runs, **Then** the case is flagged as stale and excluded from metrics (not silently dropped).
4. **Given** a maintainer replays a golden case against the real LLM provider, **When** the run completes, **Then** the result is visible with full trace context.

---

### User Story 3 - Centralized Trace For Production Debugging (Priority: P2)

As an on-call maintainer, when a user reports that an interview produced a strange summary or an error-coach hint was unhelpful, I want to retrieve the full trace of that user's invocation — every LLM call, tool call, and node transition — so that I can diagnose the root cause without relying solely on scattered structured logs.

**Why this priority**: Production debugging today requires reconstructing agent behavior from logs across multiple components. Trace centralization serves Constitution Principle V (Observability) and is a prerequisite for the self-evolution loop (US5) because trace data is what gets promoted into the golden dataset. P2 because it is infrastructural — it enables US1 (via trace→case promotion) and US5.

**Independent Test**: Can be fully tested by triggering one interview session, then querying the trace store by user and time range, and confirming the returned trace contains all node events, LLM calls, and tool calls with their inputs and outputs.

**Acceptance Scenarios**:

1. **Given** a user completes an interview, **When** the on-call queries the trace store by user and time, **Then** the full trace is returned with one event per node, one event per LLM call, and one event per tool call.
2. **Given** a trace is retrieved, **When** the on-call filters by node, **Then** only that node's events are returned with their state deltas.
3. **Given** a trace contains a failed LLM call, **When** the on-call opens that event, **Then** the error, retry count, and final outcome are visible.
4. **Given** a trace is older than the retention window, **When** the on-call queries it, **Then** a clear "expired" response is returned (not an empty result that looks like a missing trace).

---

### User Story 4 - Automated Prompt Optimization With Human Review (Priority: P3)

As a maintainer, for designated high-value nodes (e.g., interview scoring, error-coach evaluation), I want the system to propose improved prompts by searching over the golden dataset, so that I can review data-backed prompt improvements instead of guessing.

**Why this priority**: Optimization compounds value over time but is not blocking — the system works without it. P3 because it requires the golden dataset (US2) and eval pipeline (US1) to be in place first.

**Independent Test**: Can be fully tested by running the optimizer on one designated node, receiving a prompt proposal with metric delta and diff, and confirming the proposal is queued for review (not auto-applied).

**Acceptance Scenarios**:

1. **Given** a maintainer triggers optimization on the interview score node, **When** the optimizer completes, **Then** a proposal is produced containing the candidate prompt, baseline metrics, candidate metrics, and a diff against the current prompt.
2. **Given** a proposal is produced, **When** no one has reviewed it, **Then** the candidate prompt is NOT applied to production.
3. **Given** a maintainer approves a proposal, **When** the merge lands, **Then** the new prompt becomes the active baseline for future eval runs.
4. **Given** a proposal improves metrics but the maintainer rejects it on judgment (e.g., violates a constitution principle), **When** the rejection is recorded, **Then** the rejection reason is stored for future reference.

---

### User Story 5 - Self-Evolution From Production Feedback (Priority: P3)

As a maintainer, I want production traces with positive or negative user signals to be promotable into the golden dataset through a reviewed workflow, so that the eval suite improves over time based on real-world behavior.

**Why this priority**: Long-term value — the golden dataset grows and stays current. P3 because it requires US2 (golden dataset) and US3 (trace collection) to be in place, and it is not blocking day-to-day operation.

**Independent Test**: Can be fully tested by selecting one production trace, promoting it through the workflow, and confirming it appears in the next eval run as a golden case.

**Acceptance Scenarios**:

1. **Given** a production trace exists with a positive user signal (e.g., user did not re-attempt), **When** a maintainer invokes the promotion workflow, **Then** the trace is converted into a golden case candidate with PII redacted.
2. **Given** a candidate contains PII, **When** promotion is attempted, **Then** the workflow blocks until PII is redacted.
3. **Given** a promoted case is added to the golden dataset, **When** the next eval run executes, **Then** the new case is included and its result appears in the metric report.
4. **Given** an ambiguous signal (e.g., user re-attempted but original answer was plausibly correct), **When** the trace is processed, **Then** it is labeled "low confidence" and excluded from auto-promotion.

---

### Edge Cases

- What happens when the LLM provider is unavailable during an eval run? → Suite fails fast with a clear provider-unavailable error; partial results are not reported as a pass.
- What happens when a golden case schema no longer matches the current state shape? → Case is flagged "stale" and excluded from metrics; maintainer is notified to update or remove it.
- What happens when the optimizer proposes a prompt that improves metrics but is constitution-violating (e.g., shorter prompt that drops required safety instructions)? → Human review must catch it; no auto-apply path exists.
- What happens when a production trace promoted into the golden dataset later turns out to be a bad exemplar? → Maintainer can remove it; baseline is refreshed with a reviewed signature.
- What happens when the eval quota is exhausted mid-run? → Run aborts with a quota-exceeded signal; partial results are not promoted to baseline.
- What happens when two maintainers refresh the baseline simultaneously? → Last-writer-wins with a conflict warning; both signatures are recorded.

## Requirements

### Functional Requirements

**Trace collection**

- **FR-001**: System MUST record every LLM invocation with input messages, output content, model identifier, token counts, latency, and the originating node identifier.
- **FR-002**: System MUST record every tool call with arguments, return value, duration, and outcome (success/error).
- **FR-003**: System MUST record every graph node entry and exit with the state delta applied.
- **FR-004**: System MUST propagate a single trace identifier across all events belonging to one user invocation, spanning all 5 graphs and their subgraphs.
- **FR-005**: Traces MUST be queryable by user identifier, graph name, node name, time range, and outcome.

**Golden dataset**

- **FR-006**: For each of the 5 agent graphs, system MUST expose a golden dataset of at least 20 cases covering the graph's primary nodes.
- **FR-007**: Each golden case MUST include input state, expected output, a label describing what aspect it tests, and a source tag (manual or promoted-from-production).
- **FR-008**: Golden cases MUST be version-controlled alongside source code and picked up by the eval suite without manual registration.
- **FR-009**: Golden cases MUST be runnable through the real LLM provider on demand, not only through the deterministic mock.

**Eval pipeline**

- **FR-010**: System MUST run an eval suite that replays golden cases against the active model and produces a per-case and aggregate metric report.
- **FR-011**: Eval metrics MUST include answer correctness, scoring consistency across repeated runs, target-language fidelity, hallucination rate, and token cost.
- **FR-012**: The full eval suite across all 5 graphs MUST complete within 10 minutes on CI.
- **FR-013**: Eval results MUST be persisted per run with timestamp, git SHA, model identifier, and per-case verdicts for trend analysis.

**Regression gate**

- **FR-014**: When a PR changes any prompt-adjacent file, CI MUST trigger the eval suite automatically.
- **FR-015**: The gate MUST compare current run metrics against a stored baseline and block merge when any metric regresses beyond its configured threshold.
- **FR-016**: Thresholds MUST be configurable per metric per node.
- **FR-017**: Baseline refresh MUST require a reviewed workflow (reviewer signature + reason); the gate MUST NOT auto-refresh baseline on a passing run.

**Prompt optimization**

- **FR-018**: For designated high-value nodes, system MUST be able to bootstrap candidate prompts from the golden dataset.
- **FR-019**: Optimizer output MUST include the proposed prompt, baseline metrics, candidate metrics, and a diff against the current prompt.
- **FR-020**: Optimizer proposals MUST NOT be applied automatically; they require explicit human review and merge.

**Self-evolution**

- **FR-021**: System MUST capture implicit user feedback signals (re-attempt, session abandonment) on agent outputs.
- **FR-022**: System MUST expose a feedback API endpoint that frontend integration can later wire to.
- **FR-023**: System MUST allow maintainers to promote a production trace into the golden dataset through a reviewed workflow.
- **FR-024**: Promotion workflow MUST redact personally identifiable information before the trace enters the golden dataset.

### Key Entities

- **GoldenCase**: A labeled input→expected-output pair for one node; attributes include node, input state, expected output, label, source (manual/promoted), version, status (active/stale).
- **EvalRun**: A single execution of the eval suite; attributes include timestamp, git SHA, model identifier, per-case verdicts, aggregate metrics, baseline reference.
- **Trace**: A complete record of one user invocation; attributes include trace id, user id, graph name, node events, LLM calls, tool calls, outcome, retention expiry.
- **Baseline**: The stored reference metrics for a node; attributes include node, metric values, git SHA, reviewer signature, refresh timestamp.
- **PromptProposal**: An optimizer-produced candidate prompt; attributes include node, candidate prompt, baseline metrics, candidate metrics, diff, status (pending/approved/rejected), reviewer.
- **FeedbackSignal**: A user-derived signal on a trace; attributes include trace id, signal type (positive/negative/ambiguous), confidence, timestamp.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Each of the 5 agent graphs has at least 20 golden cases covering its primary nodes.
- **SC-002**: The full eval suite across all 5 graphs completes within 10 minutes on CI.
- **SC-003**: A known Chinese-fidelity regression case (zh-CN prompt producing English output) is automatically detected by the language fidelity metric with ≥95% recall.
- **SC-004**: At least one designated high-value node shows ≥5% metric improvement after a reviewed prompt optimization cycle.
- **SC-005**: No prompt-adjacent PR merges without passing the eval gate, except via the documented override (audited).
- **SC-006**: Maintainer-reported time-to-diagnose on the next 5 production agent incidents is reduced by ≥50% versus the pre-feature baseline (scattered-log debugging).
- **SC-007**: At least 10 production-trace-promoted golden cases exist in the dataset within 3 months of feature ship.

## Assumptions

- DeepSeek V4 Pro remains the sole LLM provider; no new provider is introduced.
- LangGraph remains the orchestration framework; the feature does not replace it.
- No new vector store is introduced; the optimizer operates on in-memory or existing infrastructure.
- Frontend is not modified in this feature; a feedback API endpoint is exposed but frontend wiring is deferred.
- The eval suite runs against a non-production LLM quota bucket to avoid burning user monthly quota.
- The eval suite is CLI-runnable (Constitution Principle II) and integrates into the existing CI as a pytest plugin or equivalent.
- The trace backend is a centralized, queryable store; the specific vendor (managed SaaS, self-hosted OTel-compatible, etc.) is decided in planning.
- The evaluation framework and prompt optimizer are candidate implementations to be validated in planning, not committed in this spec.
- At least one maintainer has capacity to review prompt proposals and baseline refreshes on a monthly cadence.
- Implicit feedback signals (re-attempt, abandonment) are captured server-side; explicit thumbs-up/down UI is out of scope.
- Constitution Principle III (Test-First) is directly served: prompt changes now ship with eval cases, closing the "AI prompt tasks need eval samples first" loop.
- Constitution Principle V (Observability) is extended: trace centralization adds queryable traces alongside the existing structured logs and metrics.
